import os
import json
import smtplib
import sys
import time
import boto3
from collections import defaultdict
from typing import Dict, List, Tuple, Any
from email.mime.text import MIMEText
from email.utils import formatdate
import requests

from db_manager import DbManager

API_URL = "https://api.calil.jp/check"


class LibraryAlert:
    def __init__(self, dynamodb, secrets):
        self.db_manager = DbManager(dynamodb)
        self.email = secrets["Library_Alert_EMAIL"]
        self.g_pass = secrets["Library_Alert_GOOGLE_PASS"]
        self.app_key = secrets["Library_Alert_APP_KEY"]

    def _send_request(self, db_items: List[Dict[str, str]]) -> Dict[str, Any]:
        isbn_set = set([v for dic in db_items for k, v in dic.items() if k == "ISBN"])
        library_set = set(
            [v for dic in db_items for k, v in dic.items() if k == "Library"]
        )
        payload = {
            "appkey": self.app_key,
            "isbn": ",".join(isbn_set),
            "systemid": ",".join(library_set),
            "format": "json",
            "callback": "no",
        }
        status = 1
        max_request = 20
        while status == 1 and max_request > 0:
            r = requests.get(API_URL, params=payload)
            status = r.json()["continue"]
            time.sleep(5)
            max_request -= 1
        return r.json()

    def _convert_db_items(
        self, db_items: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, str]]:
        db_dict = {}
        for db in db_items:
            db_dict.setdefault(db["ISBN"], {})
            db_dict[db["ISBN"]][db["Library"]] = db["Status"]
        return db_dict

    def _status_check(self, response, db_items) -> Dict[str, List[str]]:
        update = {}
        for isbn, libraries in response["books"].items():
            for lib, status in libraries.items():
                if status["status"] == "Error":
                    continue
                if status["libkey"] and not db_items[isbn][lib]:
                    update.setdefault(isbn, [])
                    update[isbn].append([lib, status["reserveurl"]])
                    db_items[isbn][lib] = True
        return update

    def _make_message(self, update: Dict[str, List[str]]) -> MIMEText:
        subject = "新刊入荷情報"
        bodyText = json.dumps(update)
        msg = MIMEText(bodyText)
        msg["Subject"] = subject
        msg["From"] = self.email
        msg["To"] = self.email
        msg["Date"] = formatdate()
        return msg

    def _send_email(self, msg: MIMEText) -> None:
        smtpobj = smtplib.SMTP("smtp.gmail.com", 587)
        smtpobj.starttls()
        smtpobj.login(self.email, self.g_pass)
        smtpobj.send_message(msg)
        smtpobj.close()

    def check_arrival(self):
        db_items = self.db_manager.get_db_contents()
        response = self._send_request(db_items)
        db_dict = self._convert_db_items(db_items)
        update = self._status_check(response, db_dict)
        self.db_manager.update_db(update)
        if update:
            msg = self._make_message(update)
            self._send_email(msg)


def get_ssm_params(*keys):
    secrets = {}
    ssm = boto3.client("ssm")
    response = ssm.get_parameters(
        Names=keys,
        WithDecryption=True,
    )

    for p in response["Parameters"]:
        secrets[p["Name"]] = p["Value"]

    return secrets


def lambda_handler(event, context):
    dynamodb = boto3.resource("dynamodb")
    secrets = get_ssm_params(
        "Library_Alert_EMAIL", "Library_Alert_GOOGLE_PASS", "Library_Alert_APP_KEY"
    )
    LibraryAlert(dynamodb, secrets).check_arrival()


if __name__ == "__main__":
    from dotenv import load_dotenv

    dynamodb = boto3.resource(
        "dynamodb",
        region_name="us-east-1",
        endpoint_url="http://localhost:8000",
        aws_access_key_id="ACCESS_ID",
        aws_secret_access_key="ACCESS_KEY",
    )
    load_dotenv(".env")
    secrets = {}
    secrets["Library_Alert_EMAIL"] = os.environ.get("EMAIL")
    secrets["Library_Alert_GOOGLE_PASS"] = os.environ.get("GOOGLE_PASS")
    secrets["Library_Alert_APP_KEY"] = os.environ.get("APP_KEY")
    LibraryAlert(dynamodb, secrets).check_arrival()

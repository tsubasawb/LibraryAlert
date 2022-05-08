import boto3
from boto3.dynamodb.conditions import Key
from typing import Dict, List, Tuple, Any


class DbManager:
    def __init__(self, dynamodb):
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(
            Name="Library_Alert_TABLE_NAME",
            WithDecryption=True,
        )
        self.table = dynamodb.Table(response["Parameter"]["Value"])

    def get_db_contents(self) -> List[Dict[str, str]]:
        db_items = self.table.scan()["Items"]
        # convert ton dict{ISBN, Library, Status}
        contents = []
        for item in db_items:
            if not item["BookStatus"]:
                flat_item = {}
                flat_item["Library"] = item["Library"]
                flat_item["ISBN"] = None
                flat_item["Status"] = None
                contents.append(flat_item)
            for isbn, status in item["BookStatus"].items():
                flat_item = {}
                flat_item["Library"] = item["Library"]
                flat_item["ISBN"] = isbn
                flat_item["Status"] = status
                contents.append(flat_item)
        return contents

    def update_db(self, update: Dict[str, List[str]]):
        for isbn, libraries in update.items():
            for library in libraries:
                response = self.table.query(
                    KeyConditionExpression=Key("Library").eq(library[0])
                )
                status = response["Items"][0]["BookStatus"]
                status[isbn] = True
                self.table.put_item(Item={"Library": library[0], "BookStatus": status})

    def add_book(self, isbn: str):
        for item in self.table.scan()["Items"]:
            item["BookStatus"][isbn] = False
            self.table.put_item(
                Item={"Library": item["Library"], "BookStatus": item["BookStatus"]}
            )

    def delete_book(self, isbn: str):
        for item in self.table.scan()["Items"]:
            item["BookStatus"].pop(isbn)
            self.table.put_item(
                Item={"Library": item["Library"], "BookStatus": item["BookStatus"]}
            )

    def add_library(self, library: str):
        db_items = self.table.scan()["Items"]
        new_status = {}
        if len(db_items) > 0 and len(db_items[0]["BookStatus"]) > 0:
            for isbn in db_items[0]["BookStatus"]:
                new_status[isbn] = False
        self.table.put_item(Item={"Library": library, "BookStatus": new_status})

    def delete_library(self, library: str):
        self.table.delete_item(Key={"Library": library})

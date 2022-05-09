import boto3
import decimal
import json
import os
import sys

from db_manager import DbManager

dynamodb = boto3.resource("dynamodb")
HEADERS = {
    "Access-Control-Allow-Origin": "*",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


def get_all_status(event, context):
    """
    handler for GET /
    """
    try:
        db_manager = DbManager(dynamodb)
        resp = db_manager.get_db_contents()

        status_code = 200
    except Exception as e:
        status_code = 500
        resp = {"description": f"Internal server error. {str(e)}"}
    return {
        "statusCode": status_code,
        "headers": HEADERS,
        "body": json.dumps(resp, cls=DecimalEncoder),
    }


def post_book(event, context):
    """
    handler for POST /books
    """
    try:
        body = event.get("body")
        if not body:
            raise ValueError("Invalid request. The request body is missing!")
        body = json.loads(body)

        key = "isbn"
        if not body.get(key):
            raise ValueError(f"{key} is empty")

        db_manager = DbManager(dynamodb)
        db_manager.add_book(body["isbn"])

        status_code = 201
        resp = {"description": "Successfully added a new book"}
    except ValueError as e:
        status_code = 400
        resp = {"description": f"Bad request. {str(e)}"}
    except Exception as e:
        status_code = 500
        resp = {"description": str(e)}
    return {"statusCode": status_code, "headers": HEADERS, "body": json.dumps(resp)}


def delete_book(event, context):
    """
    handler for DELETE /books/{isbn}
    """
    try:
        path_params = event.get("pathParameters", {})
        isbn = path_params.get("isbn", "")
        if not isbn:
            raise ValueError("Invalid request. The path parameter 'isbn' is missing")

        db_manager = DbManager(dynamodb)
        db_manager.delete_book(isbn)

        status_code = 204
        resp = {"description": "Successfully deleted."}
    except ValueError as e:
        status_code = 400
        resp = {"description": f"Bad request. {str(e)}"}
    except Exception as e:
        status_code = 500
        resp = {"description": str(e)}
    return {"statusCode": status_code, "headers": HEADERS, "body": json.dumps(resp)}


def post_library(event, context):
    """
    handler for POST /libraries
    """
    try:
        body = event.get("body")
        if not body:
            raise ValueError("Invalid request. The request body is missing!")
        body = json.loads(body)

        key = "systemid"
        if not body.get(key):
            raise ValueError(f"{key} is empty")

        db_manager = DbManager(dynamodb)
        db_manager.add_library(body["systemid"])

        status_code = 201
        resp = {"description": "Successfully added a new library"}
    except ValueError as e:
        status_code = 400
        resp = {"description": f"Bad request. {str(e)}"}
    except Exception as e:
        status_code = 500
        resp = {"description": str(e)}
    return {"statusCode": status_code, "headers": HEADERS, "body": json.dumps(resp)}


def delete_library(event, context):
    """
    handler for DELETE /libraries/{systemid}
    """
    try:
        path_params = event.get("pathParameters", {})
        systemid = path_params.get("systemid", "")
        if not systemid:
            raise ValueError(
                "Invalid request. The path parameter 'systemid' is missing"
            )

        db_manager = DbManager(dynamodb)
        db_manager.delete_library(systemid)

        status_code = 204
        resp = {"description": "Successfully deleted."}
    except ValueError as e:
        status_code = 400
        resp = {"description": f"Bad request. {str(e)}"}
    except Exception as e:
        status_code = 500
        resp = {"description": str(e)}
    return {"statusCode": status_code, "headers": HEADERS, "body": json.dumps(resp)}

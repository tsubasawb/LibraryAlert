from aws_cdk import (
    core,
    aws_dynamodb as ddb,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_lambda as _lambda,
    aws_ssm as ssm,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_events as events,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_cloudwatch_actions as cw_actions,
    aws_events_targets,
)
import os
import subprocess
from dotenv import load_dotenv

API_PATH = "api"
LAYER_PATH = "packages"


class LibraryAlert(core.Stack):
    def __init__(self, scope: core.App, name: str, **kwargs) -> None:
        super().__init__(scope, name, **kwargs)

        # IAM
        lambda_role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess")
        )

        # DynamoDB
        table = ddb.Table(
            self,
            "Table",
            partition_key=ddb.Attribute(name="Library", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # Lambda Function
        common_params = {
            "runtime": _lambda.Runtime.PYTHON_3_9,
            "environment": {"TABLE_NAME": table.table_name},
        }

        layer = _lambda.LayerVersion(
            self,
            "Packages",
            code=_lambda.Code.from_asset(LAYER_PATH),
            description="requests module",
        )

        library_alert_lambda = _lambda.Function(
            self,
            "LibraryAlert",
            code=_lambda.Code.from_asset(API_PATH),
            handler="library_alert.lambda_handler",
            memory_size=512,
            timeout=core.Duration.seconds(120),
            role=lambda_role,
            layers=[layer],
            **common_params,
        )
        get_all_status_lambda = _lambda.Function(
            self,
            "GetStatus",
            code=_lambda.Code.from_asset(API_PATH),
            handler="api.get_all_status",
            role=lambda_role,
            **common_params,
        )
        post_library_lambda = _lambda.Function(
            self,
            "PostLibrary",
            code=_lambda.Code.from_asset(API_PATH),
            handler="api.post_library",
            role=lambda_role,
            **common_params,
        )
        post_book_lambda = _lambda.Function(
            self,
            "PostBook",
            code=_lambda.Code.from_asset(API_PATH),
            handler="api.post_book",
            role=lambda_role,
            **common_params,
        )
        delete_library_lambda = _lambda.Function(
            self,
            "DeleteLibrary",
            code=_lambda.Code.from_asset(API_PATH),
            handler="api.delete_library",
            role=lambda_role,
            **common_params,
        )
        delete_book_lambda = _lambda.Function(
            self,
            "DeleteBook",
            code=_lambda.Code.from_asset(API_PATH),
            handler="api.delete_book",
            role=lambda_role,
            **common_params,
        )

        # API Gateway
        api = apigw.RestApi(
            self,
            "LibraryAlertApi",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        api.root.add_method(
            "GET", apigw.LambdaIntegration(get_all_status_lambda), api_key_required=True
        )

        libraries = api.root.add_resource("libraries")
        libraries.add_method(
            "POST", apigw.LambdaIntegration(post_library_lambda), api_key_required=True
        )

        libraries_systemid = libraries.add_resource("{systemid}")
        libraries_systemid.add_method(
            "DELETE",
            apigw.LambdaIntegration(delete_library_lambda),
            api_key_required=True,
        )

        books = api.root.add_resource("books")
        books.add_method(
            "POST", apigw.LambdaIntegration(post_book_lambda), api_key_required=True
        )

        books_isbn = books.add_resource("{isbn}")
        books_isbn.add_method(
            "DELETE", apigw.LambdaIntegration(delete_book_lambda), api_key_required=True
        )

        # API key
        plan = api.add_usage_plan(
            "Plan", throttle=apigw.ThrottleSettings(rate_limit=1, burst_limit=2)
        )

        key = api.add_api_key("Key")
        plan.add_api_key(key)
        plan.add_api_stage(api=api, stage=api.deployment_stage)

        # Event Bridge
        events.Rule(
            self,
            "Rule",
            schedule=events.Schedule.cron(minute="0", hour="1/1"),
            targets=[aws_events_targets.LambdaFunction(library_alert_lambda)],
        )

        # CloudWatch
        alarm = cloudwatch.Alarm(
            self,
            "Alarm",
            metric=library_alert_lambda.metric_errors(
                statistic="avg",
                period=core.Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
        )

        # SNS
        topic = sns.Topic(self, "Topic")
        alarm.add_alarm_action(cw_actions.SnsAction(topic))
        sns.Subscription(
            self,
            "LibraryAlertSubscription",
            topic=topic,
            endpoint=EMAIL,
            protocol=sns.SubscriptionProtocol.EMAIL,
        )

        # store parameters in SSM
        ssm.StringParameter(
            self,
            "TABLE_NAME",
            parameter_name="Library_Alert_TABLE_NAME",
            string_value=table.table_name,
        )
        ssm.StringParameter(
            self, "EMAIL", parameter_name="Library_Alert_EMAIL", string_value=EMAIL
        )
        ssm.StringParameter(
            self,
            "GOOGLE_PASS",
            parameter_name="Library_Alert_GOOGLE_PASS",
            string_value=GOOGLE_PASS,
        )
        ssm.StringParameter(
            self,
            "APP_KEY",
            parameter_name="Library_Alert_APP_KEY",
            string_value=APP_KEY,
        )


# install package which needs to be uploaded to lambda
subprocess.run(
    ["python3", "-m", "pip", "install", "requests", "-t", "./packages/python"]
)

# get environment variable
load_dotenv(".env")
EMAIL = os.environ.get("EMAIL")
GOOGLE_PASS = os.environ.get("GOOGLE_PASS")
APP_KEY = os.environ.get("APP_KEY")

app = core.App()
LibraryAlert(
    app,
    "LibraryAlert",
    env={
        "region": os.environ["CDK_DEFAULT_REGION"],
        "account": os.environ["CDK_DEFAULT_ACCOUNT"],
    },
)
app.synth()

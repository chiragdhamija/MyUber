# logging_interceptor.py

import grpc
from datetime import datetime

class LoggingInterceptor(grpc.UnaryUnaryClientInterceptor,
                          grpc.UnaryStreamClientInterceptor,
                          grpc.StreamUnaryClientInterceptor,
                          grpc.StreamStreamClientInterceptor):
    def __init__(self, client_role):
        self.client_role = client_role  # 'driver' or 'rider'
        self.log_file = 'log.txt'  # Specify the log file

    def log_request(self, method_name):
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {self.client_role.capitalize()} calling method: {method_name}\n"
        self.append_to_log(log_entry)

    def log_response(self, method_name, response):
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {self.client_role.capitalize()} received response from method: {method_name} - Response: {response}\n"
        self.append_to_log(log_entry)

    def append_to_log(self, log_entry):
        with open(self.log_file, 'a') as f:  # Open the log file in append mode
            f.write(log_entry)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        method_name = client_call_details.method
        self.log_request(method_name)
        response = continuation(client_call_details, request)
        self.log_response(method_name, response)
        return response

    def intercept_unary_stream(self, continuation, client_call_details, request):
        method_name = client_call_details.method
        self.log_request(method_name)
        response_iterator = continuation(client_call_details, request)
        for response in response_iterator:
            self.log_response(method_name, response)
            yield response

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        method_name = client_call_details.method
        self.log_request(method_name)
        response = continuation(client_call_details, request_iterator)
        self.log_response(method_name, response)
        return response

    def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        method_name = client_call_details.method
        self.log_request(method_name)
        response_iterator = continuation(client_call_details, request_iterator)
        for response in response_iterator:
            self.log_response(method_name, response)
            yield response

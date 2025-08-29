import grpc
from concurrent import futures
import time
import argparse
import threading
import sys

sys.path.append('../protofiles')
import load_balancer_pb2
import load_balancer_pb2_grpc

sys.path.append('../helper')  # Add the helper directory to the path
from logging_interceptor import LoggingInterceptor  # Import the logging interceptor


# Global variables
round_robin_index = 0
driver_count = {}  # Keeps track of driver counts per server

class LoadBalancer(load_balancer_pb2_grpc.LoadBalancerServiceServicer):
    def __init__(self, server_ports):
        self.server_ports = server_ports
        self.lock = threading.Lock()
        # Initialize driver count for each server port
        for port in server_ports:
            driver_count[port] = 0

    def get_next_server_ports(self):
        global round_robin_index
        with self.lock:
            # Start from the current round-robin index and create the port list in circular order
            ordered_servers = self.server_ports[round_robin_index:] + self.server_ports[:round_robin_index]
            round_robin_index = (round_robin_index + 1) % len(self.server_ports)  # Update round-robin index
        return ordered_servers

    def get_least_loaded_server(self):
        with self.lock:
            # Find the server port with the fewest drivers
            return min(driver_count, key=driver_count.get)

    def assign_driver_to_port(self, port):
        with self.lock:
            driver_count[port] += 1

    def remove_driver_from_port(self, port):
        with self.lock:
            if driver_count[port] > 0:
                driver_count[port] -= 1

    def GetServerPortForRider(self, request, context):
        server_ports = self.get_next_server_ports()
        print(f"[Load Balancer] Assigned server ports {server_ports} to rider {request.rider_id}")
        return load_balancer_pb2.ServerListResponse(server_ports=server_ports)

    def GetServerPortForDriver(self, request, context):
        # Get the server with the least number of drivers
        port = self.get_least_loaded_server()
        self.assign_driver_to_port(port)
        print(f"[Load Balancer] Assigned server port {port} to driver {request.driver_id}")
        return load_balancer_pb2.DriverPortResponse(server_port=port)
    
    def DriverExit(self, request, context):
        # Handle the driver exit notification
        print(f"[Load Balancer] Driver {request.driver_id} exiting from port {request.port}")
        self.remove_driver_from_port(request.port)
        return load_balancer_pb2.DriverExitResponse(status="Driver unregistered successfully.")

def serve(server_ports):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    interceptor = LoggingInterceptor(client_role='load_balancer')
    # server = grpc.intercept_server(server, interceptor)

     # Load SSL certificates for server
    with open('../certificates/server.crt', 'rb') as f:
        server_cert = f.read()
    with open('../certificates/server.key', 'rb') as f:
        private_key = f.read()
    with open('../certificates/ca.crt', 'rb') as f:
        ca_cert = f.read()

    # Use mTLS for mutual authentication (client and server)
    server_credentials = grpc.ssl_server_credentials(
        [(private_key, server_cert)],
        root_certificates=ca_cert,
        require_client_auth=True
    )
    load_balancer_pb2_grpc.add_LoadBalancerServiceServicer_to_server(LoadBalancer(server_ports), server)
    server.add_secure_port('[::]:4000', server_credentials)  # Load Balancer on port 4000
    server.start()
    print(f"[Load Balancer] Load Balancer is running on port 4000 with servers: {server_ports}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    # Parse command-line arguments for live server ports
    parser = argparse.ArgumentParser(description="Start the load balancer for ride-sharing servers.")
    parser.add_argument('--ports', nargs='+', help='List of live server ports, e.g., --ports 5001 5002 5003', required=True)
    
    args = parser.parse_args()

    # Serve the load balancer with the provided ports
    serve(args.ports)

import grpc
import sys
import time

# Add the necessary directories to the path
sys.path.append('../protofiles')  # Add the protofiles directory to the path
import load_balancer_pb2
import load_balancer_pb2_grpc
import ride_sharing_pb2
import ride_sharing_pb2_grpc

sys.path.append('../helper')  # Add the helper directory to the path
from logging_interceptor import LoggingInterceptor  # Import the logging interceptor


def get_server_ports_from_load_balancer(rider_id):
    
    with open('../certificates/rider_client.crt', 'rb') as f:
        client_cert = f.read()
    with open('../certificates/rider_client.key', 'rb') as f:
        private_key = f.read()
    with open('../certificates/ca.crt', 'rb') as f:
        ca_cert = f.read()

    # Set up SSL credentials for the client
    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=private_key,
        certificate_chain=client_cert
    )
    channel = grpc.secure_channel('localhost:4000', credentials)
    stub = load_balancer_pb2_grpc.LoadBalancerServiceStub(channel)

    request = load_balancer_pb2.RiderRequest(rider_id=rider_id)
    response = stub.GetServerPortForRider(request)
    return response.server_ports


def request_ride(rider_id, pickup_location, destination):
    ports = get_server_ports_from_load_balancer(rider_id)
    print(ports)
    interceptor = LoggingInterceptor(client_role='rider')  # Create an instance of the interceptor
    for port in ports :
        
        with open('../certificates/rider_client.crt', 'rb') as f:
            client_cert = f.read()
        with open('../certificates/rider_client.key', 'rb') as f:
            private_key = f.read()
        with open('../certificates/ca.crt', 'rb') as f:
            ca_cert = f.read()

        # Set up SSL credentials for the rider client
        credentials = grpc.ssl_channel_credentials(
            root_certificates=ca_cert,
            private_key=private_key,
            certificate_chain=client_cert
        )

        channel = grpc.intercept_channel(grpc.secure_channel(f'localhost:{port}', credentials), interceptor)
        stub = ride_sharing_pb2_grpc.RideSharingServiceStub(channel)


        print(f"[Rider {rider_id}] Requesting a ride from server on port {port}...")
        request = ride_sharing_pb2.RideRequest(rider_id=rider_id, pickup_location=pickup_location, destination=destination)
        response = stub.RequestRide(request)
        print(f"[Rider {rider_id}] Ride response: {response.status}, Ride ID: {response.ride_id}, Assigned Driver: {response.assigned_driver}")
        # Polling for ride status
        if response.status == 'assigned':
            while True:
                status_response = stub.GetRideStatus(ride_sharing_pb2.RideStatusRequest(ride_id=response.ride_id))
                print(f"[Rider {rider_id}] Current ride status: {status_response.status}")
                if status_response.status in ['completed', 'cancelled', 'rejected']:
                    if status_response.status == 'completed' :
                        return
                    else : 
                        break
                time.sleep(3)  # Wait before polling again
        else:
            print(f"[Rider {rider_id}] No drivers available on server {port}, trying next server...")

    print(f"[Rider {rider_id}] No drivers available on any server.")

if __name__ == '__main__':
    rider_id = input("Enter Rider ID: ")
    pickup_location = input("Enter Pickup Location: ")
    destination = input("Enter Destination: ")
    request_ride(rider_id, pickup_location, destination)

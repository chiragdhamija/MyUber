import grpc
import time
import signal
import sys


sys.path.append('../protofiles')  # Add the protofiles directory to the path
import load_balancer_pb2
import load_balancer_pb2_grpc
import ride_sharing_pb2
import ride_sharing_pb2_grpc

sys.path.append('../helper')  # Add the helper directory to the path
from logging_interceptor import LoggingInterceptor  # Import the logging interceptor



def get_port_from_load_balancer(driver_id):
    # Connect to the load balancer's port
    channel = grpc.secure_channel('localhost:4000', get_credentials())
    stub = load_balancer_pb2_grpc.LoadBalancerServiceStub(channel)
    response = stub.GetServerPortForDriver(load_balancer_pb2.DriverRequest(driver_id=driver_id))
    return response.server_port

def get_credentials():
    # Load SSL certificates for client
    with open('../certificates/driver_client.crt', 'rb') as f:
        client_cert = f.read()
    with open('../certificates/driver_client.key', 'rb') as f:
        private_key = f.read()
    with open('../certificates/ca.crt', 'rb') as f:
        ca_cert = f.read()

    # Set up SSL credentials for the driver client
    return grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=private_key,
        certificate_chain=client_cert
    )

def handle_driver(driver_id):
    port = get_port_from_load_balancer(driver_id)
    print(f"[Driver {driver_id}] Assigned server port: {port}")
    interceptor = LoggingInterceptor(client_role='driver')
    
    # Create a gRPC channel with the logging interceptor
    channel = grpc.intercept_channel(grpc.secure_channel(f'localhost:{port}', get_credentials()), interceptor)
    stub = ride_sharing_pb2_grpc.RideSharingServiceStub(channel)
 

    # Register the driver
    register_response = stub.RegisterDriver(ride_sharing_pb2.RegisterDriverRequest(driver_id=driver_id))
    print(f"[Driver {driver_id}] Registration status: {register_response.status} on port {port}")

    def unregister_driver(signum, frame):
        # Unregister the driver before exiting
        unregister_response = stub.UnregisterDriver(ride_sharing_pb2.UnregisterDriverRequest(driver_id=driver_id))
        print(f"[Driver {driver_id}] Unregistration status: {unregister_response.status}")
        lb_channel = grpc.secure_channel('localhost:4000', get_credentials())  # Load balancer's port
        lb_stub = load_balancer_pb2_grpc.LoadBalancerServiceStub(lb_channel)
        lb_response = lb_stub.DriverExit(load_balancer_pb2.DriverExitRequest(driver_id=driver_id, port=port))
        print(f"[Driver {driver_id}] Load Balancer response on exit: {lb_response.status}")  # Capture and print response
        sys.exit(0)

    # Register the signal handler for graceful exit
    signal.signal(signal.SIGINT, unregister_driver)

    while True:
        print(f"[Driver {driver_id}] Waiting for a ride to be assigned...")

        # Poll the server to check for available rides
        time.sleep(2)  # Polling interval

        # Check if any rides have been assigned to this driver
        response = stub.GetAssignedRide(ride_sharing_pb2.AssignedRideRequest(driver_id=driver_id))
        if response.ride_id:
            print(f"[Driver {driver_id}] Ride assigned: {response.ride_id} from {response.pickup_location} to {response.destination}")
            accept = input(f"[Driver {driver_id}] Do you accept this ride? (yes/no): ").strip().lower()

            if accept == 'yes':
                # Simulate accepting the ride
                accept_response = stub.AcceptRide(ride_sharing_pb2.AcceptRideRequest(driver_id=driver_id, ride_id=response.ride_id))
                print(f"[Driver {driver_id}] Ride acceptance status: {accept_response.status}")

                if accept_response.status == 'ride_accepted':
                    # Simulate ride completion after some time
                    input(f"[Driver {driver_id}] Press Enter to mark the ride as completed...")  # Driver inputs when ride is completed
                    complete_response = stub.CompleteRide(ride_sharing_pb2.RideCompletionRequest(driver_id=driver_id, ride_id=response.ride_id))
                    print(f"[Driver {driver_id}] Ride completion status: {complete_response.status}")
            else:
                # Simulate rejecting the ride
                reject_response = stub.RejectRide(ride_sharing_pb2.RejectRideRequest(driver_id=driver_id, ride_id=response.ride_id))
                print(f"[Driver {driver_id}] Ride rejection status: {reject_response.status}")
        else:
            print(f"[Driver {driver_id}] No rides currently assigned.")

if __name__ == '__main__':
    driver_id = input("Enter Driver ID: ")
    # port = input("Enter server port (5001, 5002, or 5003): ")
    handle_driver(driver_id)

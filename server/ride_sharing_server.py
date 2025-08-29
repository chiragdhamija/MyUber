import grpc
from concurrent import futures
import time
import uuid
import threading
import random
import sys

sys.path.append('../protofiles')
import ride_sharing_pb2
import ride_sharing_pb2_grpc

sys.path.append('../helper')  
from logging_interceptor import LoggingInterceptor  

class RideSharingService(ride_sharing_pb2_grpc.RideSharingServiceServicer):
    def __init__(self):
        self.rides = {}  # Holds active rides
        self.drivers = {}  # Holds available drivers
        self.rejected_rides = {}  # Holds rejected rides for each driver

    def RequestRide(self, request, context):
        ride_id = str(uuid.uuid4())
        self.rides[ride_id] = {
            'rider_id': request.rider_id,
            'pickup_location': request.pickup_location,
            'destination': request.destination,
            'assigned_driver': None,
            'status': 'waiting_for_acceptance',
            'accept_thread': None
        }
        
        # Try to assign a driver
        available_driver = self.get_available_driver(ride_id)  # Pass ride_id to avoid rejected rides
        if available_driver:
            self.rides[ride_id]['assigned_driver'] = available_driver
            self.rides[ride_id]['status'] = 'waiting_for_acceptance'
            self.start_timeout_thread(ride_id, available_driver)  # Start timeout handling
            response = ride_sharing_pb2.RideResponse(
                status='assigned',
                ride_id=ride_id,
                assigned_driver=available_driver
            )
            print(f"[Server] Ride assigned: {ride_id} to Driver {available_driver}")
            return response
        else:
            response = ride_sharing_pb2.RideResponse(status='no_drivers_available')
            print(f"[Server] No drivers available for rider {request.rider_id}")
            return response

    def start_timeout_thread(self, ride_id, driver_id):
        def timeout_handler():
            time.sleep(10)  # Timeout period in seconds
            ride = self.rides.get(ride_id)
            if ride and ride['status'] == 'waiting_for_acceptance':
                print(f"[Server] Timeout: Driver {driver_id} did not respond in time.")
                self.add_to_rejected_rides(driver_id, ride_id)
                self.reassign_ride(ride_id)

        # Create and start the timeout thread
        thread = threading.Thread(target=timeout_handler)
        thread.start()
        self.rides[ride_id]['accept_thread'] = thread
    
    def add_to_rejected_rides(self, driver_id, ride_id):
        if driver_id not in self.rejected_rides:
            self.rejected_rides[driver_id] = set()
        self.rejected_rides[driver_id].add(ride_id)
        # print(f"[Server] Ride {ride_id} added to rejected rides for Driver {driver_id}.")

    def reassign_ride(self, ride_id):
        ride = self.rides.get(ride_id)
        if ride:
            new_driver = self.get_available_driver(ride_id)  # Check for rejected rides
            if new_driver:
                ride['assigned_driver'] = new_driver
                print(f"[Server] Reassigned ride {ride_id} to Driver {new_driver}.")
                ride['status'] = 'waiting_for_acceptance'
                self.start_timeout_thread(ride_id, new_driver)  # Start new timeout
            else:
                ride['status'] = 'cancelled'  # No available drivers
                print(f"[Server] Ride {ride_id} cancelled due to no available drivers.")

    def RegisterDriver(self, request, context):
        self.register_driver(request.driver_id)
        return ride_sharing_pb2.AcceptRideResponse(status='driver_registered')
    
    def AssignRide(self, request, context):
        ride_id = self.assign_ride(request.driver_id)
        if ride_id:
            return ride_sharing_pb2.AssignRideResponse(ride_id=ride_id)
        return ride_sharing_pb2.AssignRideResponse(ride_id="")

    def GetRideStatus(self, request, context):
        ride = self.rides.get(request.ride_id)
        if ride:
            return ride_sharing_pb2.RideStatusResponse(status=ride['status'])
        return ride_sharing_pb2.RideStatusResponse(status='no_such_ride')

    def AcceptRide(self, request, context):
        ride = self.rides.get(request.ride_id)
        if ride and ride['assigned_driver'] == request.driver_id:
            ride['status'] = 'in_progress'
            ride['accept_thread'].join()  # Ensure timeout thread is finished
            self.drivers[request.driver_id] = 'busy'
            response = ride_sharing_pb2.AcceptRideResponse(status='ride_accepted', ride_id=request.ride_id)
            print(f"[Server] Driver {request.driver_id} accepted ride {request.ride_id}")
            return response
        return ride_sharing_pb2.AcceptRideResponse(status='ride_already_accepted')

    def RejectRide(self, request, context):
        ride = self.rides.get(request.ride_id)
        if ride and ride['assigned_driver'] == request.driver_id:
            ride['assigned_driver'] = None
            ride['status'] = 'waiting_for_acceptance'
            ride['accept_thread'].join()  # Ensure timeout thread is finished
            
            # Add the rejected ride to the driver's list of rejected rides
            if request.driver_id not in self.rejected_rides:
                self.rejected_rides[request.driver_id] = set()
            self.rejected_rides[request.driver_id].add(request.ride_id)

            self.start_timeout_thread(request.ride_id, self.get_available_driver())  # Attempt to reassign
            response = ride_sharing_pb2.RejectRideResponse(status='ride_rejected')
            print(f"[Server] Driver {request.driver_id} rejected ride {request.ride_id}")
            return response
        return ride_sharing_pb2.RejectRideResponse(status='no_such_ride')

    def CompleteRide(self, request, context):
        ride = self.rides.get(request.ride_id)
        if ride and ride['assigned_driver'] == request.driver_id:
            ride['status'] = 'completed'
            self.drivers[request.driver_id] = 'available'
            response = ride_sharing_pb2.RideCompletionResponse(status='ride_completed')
            print(f"[Server] Ride {request.ride_id} completed by Driver {request.driver_id}")
            return response
        return ride_sharing_pb2.RideCompletionResponse(status='ride_not_found')

    def get_available_driver(self, ride_id=None):
        available_drivers = [driver_id for driver_id, status in self.drivers.items() if status == 'available']
        if ride_id:
            # Exclude drivers who have rejected the current ride
            rejected_drivers = {driver_id for driver_id in self.rejected_rides if ride_id in self.rejected_rides[driver_id]}
            available_drivers = list(set(available_drivers) - rejected_drivers)
        
        if available_drivers:
            return random.choice(available_drivers)  # Select a random available driver
        return None

    def register_driver(self, driver_id):
        self.drivers[driver_id] = 'available'
        print(f"[Server] Driver {driver_id} registered.")

    def UnregisterDriver(self, request, context):
        self.unregister_driver(request.driver_id)
        return ride_sharing_pb2.UnregisterDriverResponse(status='driver_unregistered')

    def unregister_driver(self, driver_id):
        if driver_id in self.drivers:
            del self.drivers[driver_id]
            print(f"[Server] Driver {driver_id} unregistered.")

    def GetAssignedRide(self, request, context):
        for ride_id, ride in self.rides.items():
            if ride['assigned_driver'] == request.driver_id and ride['status'] == 'waiting_for_acceptance':
                return ride_sharing_pb2.AssignedRideDetails(
                    pickup_location=ride['pickup_location'],
                    destination=ride['destination'],
                    ride_id=ride_id
                )
        return ride_sharing_pb2.AssignedRideDetails()  # Return empty if no rides are assigned

    def assign_ride(self, driver_id):
        # Logic to assign a ride (this is a placeholder)
        ride_id = None
        for id, ride in self.rides.items():
            if ride['assigned_driver'] is None:  # Check if ride is available for assignment
                ride['assigned_driver'] = driver_id
                ride['status'] = 'waiting_for_acceptance'
                ride_id = id
                print(f"[Server] Assigned ride {ride_id} to driver {driver_id}.")
                break
        return ride_id

def serve():
    if len(sys.argv) < 2:
        print("Please provide the port number as a command-line argument.")
        sys.exit(1)
    port = sys.argv[1]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    interceptor = LoggingInterceptor(client_role='server')  # Adjust role as needed
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

    # Add RideSharing service to the server
    ride_sharing_pb2_grpc.add_RideSharingServiceServicer_to_server(RideSharingService(), server)

    # Use the provided port from command-line arguments
    server.add_secure_port(f'[::]:{port}', server_credentials)

    server.start()
    print(f"[Server] Ride Sharing Service is running on port {port}...")
    
    try:
        while True:
            time.sleep(86400)  # Keep the server running
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()


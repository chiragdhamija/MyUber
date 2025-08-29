# How to Run the Code

## 1. Install Required Libraries  
Begin by installing the necessary libraries. Run the following command in your terminal:

```bash
pip install grpcio grpcio-tools numpy
sudo apt install openssl
```

## 2. Generate Python Code from Protobuf Files  
Navigate to the `protofiles` directory and execute the following commands to generate Python code from the `ride_sharing.proto` and `load_balancer.proto` files:

```bash
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ride_sharing.proto
python3 -m grpc_tools.protoc -I=. --python_out=. --grpc_python_out=. load_balancer.proto
```

## 3. Generate Certificates for Authentication  
In the `certificates` directory, open the terminal and run the commands below to generate the necessary certificates:

### Generate CA Certificate:
```bash
openssl genpkey -algorithm RSA -out ca.key
openssl req -new -x509 -key ca.key -out ca.crt -days 365 -subj "/CN=RideSharingCA"
```

### Generate Server Certificate:
```bash
openssl genpkey -algorithm RSA -out server.key
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"  # Change CN to localhost
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365
```

### Generate Rider Client Certificate:
```bash
openssl genpkey -algorithm RSA -out rider_client.key
openssl req -new -key rider_client.key -out rider_client.csr -subj "/CN=RiderClient"
openssl x509 -req -in rider_client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out rider_client.crt -days 365
```

### Generate Driver Client Certificate:
```bash
openssl genpkey -algorithm RSA -out driver_client.key
openssl req -new -key driver_client.key -out driver_client.csr -subj "/CN=DriverClient"
openssl x509 -req -in driver_client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out driver_client.crt -days 365
```

## 4. Start All the Servers  
Navigate to the `server` directory and start all the servers using the following command (avoid using port number 4000, as it will be designated for the load balancer):

```bash
python3 ride_sharing_server.py port_number
```

**Example:**  
To start the server, run:

```bash
python3 ride_sharing_server.py 5050
```

## 5. Start the Load Balancer Server  
In the `server` directory, start the load balancer (which operates on port number 4000) by executing the command:

```bash
python3 load_balance.py
```

## 6. Run One or More Driver Clients  
Navigate to the `client` directory and start multiple driver clients by executing the following command multiple times:

```bash
python3 driver_client.py
```

Enter a unique driver ID to begin. The driver will connect to a running server and wait for a ride to be assigned. The driver can accept or reject the ride by responding "yes" or "no." If accepted, the ride can be marked complete by pressing the ENTER key. To exit and deregister, the driver can press CTRL+C.

## 7. Run One or More Rider Clients  
In the `client` directory, start multiple rider clients by executing the rider client code multiple times:

```bash
python3 rider_client.py
```

Enter a unique rider ID and specify the pickup and destination locations. The rider will wait for a driver to be assigned and will receive constant updates about their ride.

## 8. Assumptions
- Once a driver accepts a ride, they must complete it and cannot exit midway.
- During a client's ride request, new drivers will not be able to join until the ride is assigned or rider gets a message of no drivers available.
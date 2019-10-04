from stock_exchange_pb2 import *
import stock_exchange_pb2_grpc
import grpc
from pprint import pprint
import time

def main():
	channel = grpc.insecure_channel('localhost:50051')
	stub = stock_exchange_pb2_grpc.StockExchangeStub(channel)

	now = int(time.time()) - 30

	bob_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Bob", created_at=now, buy=True, quantity=1, price=95, stock="APPL")))
	bill_order1 = stub.OrderCreate(OrderCreateRequest(order=Order(user="Bill", created_at=now+1, buy=True, quantity=1, price=97, stock="APPL")))
	bill_order2 = stub.OrderCreate(OrderCreateRequest(order=Order(user="Bill", created_at=now+2, buy=True, quantity=2, price=95, stock="APPL")))
	sam_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Sam", created_at=now+3, buy=False, quantity=2, price=102, stock="APPL")))
	sara_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Sara", created_at=now+4, buy=False, quantity=3, price=103, stock="APPL")))
	simon_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Simon", created_at=now+5, buy=False, quantity=10, price=120, stock="APPL")))

	print("*******   Sam's Order")
	print(stub.OrderStatus(OrderIdRequest(order_id=sam_order.order_id)))
	print()

	print("*******   Bart's Order")
	bart_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Bart", created_at=now+6, buy=True, quantity=3, price=104, stock="APPL")))
	print(bart_order)
	print()

	print("*******   Sam's Order")
	print(stub.OrderStatus(OrderIdRequest(order_id=sam_order.order_id)))
	print()

	print("*******   Sara's Order")
	print(stub.OrderStatus(OrderIdRequest(order_id=sara_order.order_id)))
	print()

	print("*******   Betty's Order")
	betty_order = stub.OrderCreate(OrderCreateRequest(order=Order(user="Betty", created_at=now+7, buy=False, quantity=1, price=96, stock="APPL")))
	print(betty_order)
	print()

	print("*******   Simon's Order")
	simon_order = stub.OrderCancel(OrderIdRequest(order_id=simon_order.order_id))
	print(simon_order)
	print()

	print("*******   StockVolume1h")
	print(stub.StockVolume1h(StockRequest(stock="APPL")))
	print()

	print("*******   StockPrice1h")
	print(stub.StockPrice1h(StockRequest(stock="APPL")))
	print()

	print("*******   OHLC")
	print(stub.OHLC(OHLCRequest(stock="APPL", start_time=now-1000, end_time=now+1000)))
	print()

if __name__ == "__main__":
	main()

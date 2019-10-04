from concurrent import futures
import logging
import time

import grpc

from stock_exchange_pb2 import *
import stock_exchange_pb2_grpc

class StockExchangeServicer(stock_exchange_pb2_grpc.StockExchangeServicer):

    def __init__(self):
        self.maxOrderId = 0
        self.activeOrders = {}
        self.inactiveOrders = {}
        self.orderStatus = {}
        self.userOrders = {}
        self.remainingQuantity = {}
        self.stockDetails = {}
        self.lastHourStockDetails = {}
        self.stockVolume1h = {}
        self.stockPrice1h = {}

    def _RemoveStock1h(self):
        for stock in self.lastHourStockDetails.keys():
            delete_upto = 0
            current_time = int(time.time())
            volume = self.stockVolume1h[stock]
            average_price = self.stockPrice1h[stock]
            for details in self.lastHourStockDetails[stock]:
                if details["time"] < current_time - 3600:
                    average_price = (average_price * volume - details["price"] * details["quantity"]) / (volume - details["quantity"])
                    volume -= details["quantity"]
                    delete_upto += 1
                else:
                    break
            self.lastHourStockDetails[stock] = self.lastHourStockDetails[stock][delete_upto:]
            self.stockVolume1h[stock] = volume
            self.stockPrice1h[stock] = average_price

    def _AddStockTo1hDetails(self, stock, stock_detail):
        volume = self.stockVolume1h[stock]
        average_price = self.stockPrice1h[stock]
        average_price = (average_price * volume + stock_detail["price"] * stock_detail["quantity"]) / (volume + stock_detail["quantity"])
        volume += stock_detail["quantity"]
        self.stockVolume1h[stock] = volume
        self.stockPrice1h[stock] = average_price
        self.lastHourStockDetails[stock].append(stock_detail)

    def _MatchBuyOrder(self, new_order_id):
        minimum_price = self.activeOrders[new_order_id].price+1
        best_order_id = None
        for order_id, order in self.activeOrders.items():
            if order.stock != self.activeOrders[new_order_id].stock:
                continue
            if order.buy:
                continue
            if order.price < minimum_price:
                minimum_price = order.price
                best_order_id = order_id
            elif order.price == minimum_price:
                if not best_order_id:
                    best_order_id = order_id
                elif order.created_at < self.activeOrders[best_order_id].created_at:
                    best_order_if = order_id
        return best_order_id

    def _MatchSellOrder(self, new_order_id):
        maximum_price = self.activeOrders[new_order_id].price-1
        best_order_id = None
        for order_id, order in self.activeOrders.items():
            if order.stock != self.activeOrders[new_order_id].stock:
                continue
            if not order.buy:
                continue
            if order.price > maximum_price:
                maximum_price = order.price
                best_order_id = order_id
            elif order.price == maximum_price:
                if not best_order_id:
                    best_order_id = order_id
                elif order.created_at < self.activeOrders[best_order_id].created_at:
                    best_order_id = order_id
        return best_order_id

    def _MatchOrder(self, new_order_id):
        is_buy = self.activeOrders[new_order_id].buy
        stock = self.activeOrders[new_order_id].stock
        best_order_id = None

        if is_buy:
            best_order_id = self._MatchBuyOrder(new_order_id)
        else:
            best_order_id = self._MatchSellOrder(new_order_id)
            
        if best_order_id is None:
            return False

        quantity = min(self.remainingQuantity[new_order_id], self.remainingQuantity[best_order_id])
        self.remainingQuantity[new_order_id] -= quantity
        self.remainingQuantity[best_order_id] -= quantity

        price = self.activeOrders[best_order_id].price
        match = OrderMatch(price=price,
            quantity = quantity,
            created_at = int(time.time())
        )

        self.orderStatus[new_order_id].matches.append(match)
        self.orderStatus[best_order_id].matches.append(match)

        stock_detail = {
            "price": price,
            "quantity": quantity,
            "time": int(time.time())
        }
        self.stockDetails[stock].append(stock_detail)
        self._AddStockTo1hDetails(stock, stock_detail)

        if self.remainingQuantity[best_order_id] == 0:
            self._DeactivateOrder(best_order_id)
        if self.remainingQuantity[new_order_id] == 0:
            self._DeactivateOrder(new_order_id)
        return True

    def _DeactivateOrder(self, order_id):
        if order_id not in self.activeOrders:
            return
        self.inactiveOrders[order_id] = self.activeOrders[order_id]
        del self.activeOrders[order_id]
        self.orderStatus[order_id].active = False

    def OrderCreate(self, request, context):
        self.maxOrderId += 1

        order_id = self.maxOrderId
        self.activeOrders[order_id] = request.order

        stock = request.order.stock
        if stock not in self.stockDetails:
            self.stockDetails[stock] = []
            self.lastHourStockDetails[stock] = []
            self.stockPrice1h[stock] = 0
            self.stockVolume1h[stock] = 0
        
        user = request.order.user
        if user not in self.userOrders:
            self.userOrders[user] = []

        self.userOrders[user].append(order_id)
        self.orderStatus[order_id] = OrderStatusResponse(order_id=order_id, active=True, matches=[])
        self.remainingQuantity[order_id] = request.order.quantity

        matched = self._MatchOrder(order_id)
        while matched and self.orderStatus[order_id].active:
            matched = self._MatchOrder(order_id)

        self._RemoveStock1h()
        return self.orderStatus[order_id]

    def OrderStatus(self, request, context):
        return self.orderStatus[request.order_id]

    def OrderCancel(self, request, context):
        self._DeactivateOrder(request.order_id)
        return self.orderStatus[request.order_id]

    def UserOrders(self, request, context):
        requested_orders = []
        for order_id in self.userOrders[user]:
            created_at = self.orders[order_id].created_at
            if created_at < request.start_time:
                continue
            if created_at > request.end_time:
                break
            requested_orders.append(self.orderStatus[order_id])
        
        return MultiOrderStatusResponse(orders=requested_orders)

    def StockVolume1h(self, request, context):
        return VolumeResponse(volume=self.stockVolume1h[request.stock])
    
    def StockPrice1h(self, request, context):
        return PriceResponse(price=self.stockPrice1h[request.stock])

    def OHLC(self, request, response):
        open = -1
        high = -1
        low = -1
        close = -1
        volume = 0
        for detail in self.stockDetails[request.stock]:
            if detail["time"] < request.start_time:
                continue
            if detail["time"] > request.end_time:
                break
            if open == -1:
                open = detail["price"]
            if low == -1:
                low = detail["price"]
            high = max(high, detail["price"])
            low = min(low, detail["price"])
            close = detail["price"]
            volume += detail["quantity"]
        return OHLCResponse(open=open, high=high, low=low, close=close, volume=volume)
            
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    stock_exchange_pb2_grpc.add_StockExchangeServicer_to_server(
        StockExchangeServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig()
    serve()
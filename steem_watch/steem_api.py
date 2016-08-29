#!/usr/bin/env python3

# Every time we get a block from any node, wait two seconds and then send it to all nodes that haven't yet told us about it.

import itertools
import json
import time

import tornado.concurrent
import tornado.gen
import tornado.locks
import tornado.queues
import tornado.websocket

class SteemException(Exception):
    def __init__(self, msg="", steem_msg=""):
        Exception.__init__(self, msg)
        self.steem_msg = steem_msg

class ApiMethod(object):
    def __init__(self, call_func, api_name, method_name):
        self.call_func = call_func
        self.api_name = api_name
        self.method_name = method_name
        return

    async def __call__(self, *args, **kwargs):
        if len(kwargs) > 0:
            if len(args) > 0:
                raise SteemException("Cannot specify args and kwargs simultaneously in steemd API call")
            args = [kwargs]
        result = await self.call_func( self.api_name, self.method_name, args )
        return result

class ApiObject(object):
    def __init__(self, call_func, api_name):
        self.call_func = call_func
        self.api_name = api_name
        return

    def __getattr__(self, method_name):
        return ApiMethod(self.call_func, self.api_name, method_name)

class ApiNode(object):
    class State(object):
        DISCONNECTED = 1
        HANDSHAKE = 2
        CONNECTED = 3

        STATE_BEGIN = 1
        STATE_END = 4

    def __init__(self,
        websocket_url="",
        io_loop=None,
        on_connect=None,
        retry_wait_time=60,
        ):
        self.websocket_url = websocket_url
        self.io_loop = io_loop
        self.on_connect = on_connect
        self.retry_wait_time = retry_wait_time

        self.state = ApiNode.State.DISCONNECTED
        self.ws_conn = None
        self.id_count = itertools.count(1)
        self.cbid_count = itertools.count(1)
        self.notify_id_to_cb = {}
        self.call_id_to_future = {}

        self.state_event = {st : tornado.locks.Event() for st in range(ApiNode.State.STATE_BEGIN, ApiNode.State.STATE_END)}
        return

    def _change_state(self, new_state):
        if new_state == self.state:
            return
        self.state_event[self.state].clear()
        self.state_event[new_state].set()
        self.state = new_state
        return

    def start(self):
        self.io_loop.add_callback( lambda : self._main_loop() )
        return

    def stop(self):
        # Right now stop() does nothing
        return

    async def _launch_on_connect(self):
        if self.on_connect is not None:
            result = self.on_connect()
            if result is not None:
                await result
        if self.state == ApiNode.State.HANDSHAKE:
            self._change_state(ApiNode.State.CONNECTED)
        return

    async def _main_loop(self):
        is_first_time = True
        while True:
            self._change_state( ApiNode.State.DISCONNECTED )
            if is_first_time:
                is_first_time = False
            else:
                await tornado.gen.sleep(self.retry_wait_time)
            self.notify_id_to_cb.clear()
            for fut in self.call_id_to_future.values():
                fut.set_exception( SteemException, "steemd RPC connection closed" )
            self.call_id_to_future.clear()
            try:
                self.ws_conn = await tornado.websocket.websocket_connect( url=self.websocket_url, io_loop=self.io_loop, connect_timeout=60 )
            except Exception:
                print("couldn't connect to", self.websocket_url, "trying again in "+str(self.retry_wait_time)+" seconds")
                continue

            self._change_state( ApiNode.State.HANDSHAKE )
            self.io_loop.add_callback( self._launch_on_connect )

            while True:
                try:
                    json_msg = await self.ws_conn.read_message()
                except Exception as e:
                    print("Caught exception in ws_conn.read_message()")
                    print(e)
                    break
                if json_msg is None:
                    print("Connection closed, bail")
                    break
                msg = json.loads(json_msg)
                if "result" in msg:
                    msg_id = msg["id"]
                    self.call_id_to_future[ msg_id ].set_result( msg["result"] )
                    del self.call_id_to_future[ msg_id ]
                elif "error" in msg:
                    msg_id = msg["id"]
                    self.call_id_to_future[ msg_id ].set_exception( SteemException("steemd RPC API returned error", steem_msg=msg["error"]) )
                    del self.call_id_to_future[ msg_id ]
                elif msg.get("method") == "notice":
                    cb_id, cb_params = msg["params"]
                    self.io_loop.add_callback( self.notify_id_to_cb[ cb_id ], *cb_params )
                else:
                    print("Unable to parse message from server")
                    print(repr(msg))
                    continue
        return

    async def wait_for_connection(self):
        await self.state_event[ ApiNode.State.CONNECTED ].wait()
        return

    async def call(self, api_name, method_name, args):
        call_id = next(self.id_count)
        call_object = {"json_rpc" : "2.0", "id" : call_id, "method" : "call", "params" : [api_name, method_name, args]}
        call_json = json.dumps(call_object, sort_keys=True, separators=(",", ":"))
        fut = tornado.concurrent.Future()
        self.call_id_to_future[ call_id ] = fut
        self.ws_conn.write_message(call_json)
        result = await fut
        return result

    def get_api(self, api_name):
        return ApiObject(self.call, api_name)

    def cb(self, fn):
        cbid = next(self.cbid_count)
        self.notify_id_to_cb[ cbid ] = fn
        return cbid

async def main():
    node = ApiNode(io_loop=io_loop, websocket_url="ws://127.0.0.1:8790")
    node.start()
    await node.wait_for_connection()
    db_api = node.get_api("database_api")
    block = await db_api.get_block(9500)
    print("block:", block)
    block_queue = tornado.queues.Queue()
    await db_api.set_block_applied_callback( node.cb(block_queue.put_nowait) )
    n = 0
    async for block in block_queue:
        print(block)
        n += 1
        if n >= 5:
            break
    return

if __name__ == "__main__":
    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.add_callback(main)
    io_loop.start()

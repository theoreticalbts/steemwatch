
import argparse
import json

from . import asyncutil
from . import steem_api

import tornado

import sys

def parse_number(n_str):
    if n_str.startswith("0x"):
        return int(n_str[2:], 16)
    if n_str.endswith("h") or n_str.endswith("H"):
        return int(n_str[:-1], 16)
    return int(n_str)

def parse_block_num(head_block_num, n_str):
    if n_str == "":
        return -1
    if n_str.startswith("+"):
        return head_block_num+parse_number(n_str[1:])
    if n_str.startswith("-"):
        return head_block_num-parse_number(n_str[1:])
    return parse_number(n_str)

def parse_range(head_block_num, r_str):
    if r_str == "":
        return (head_block_num, -1)
    if ":" not in r_str:
        a = parse_block_num(head_block_num, r_str)
        return (a, a+1)
    lhs, rhs = r_str.split(":")
    a = parse_block_num(head_block_num, lhs)
    b = parse_block_num(head_block_num, rhs)
    return (a, b)

class BlockDump(object):
    def __init__(self, steem_node, dump_dir):
        self.steem_node = steem_node
        self.dump_dir = dump_dir
        self.chunk_size = 20000
        return

    @functools.lru_cache(5)
    def get_chunk(self, chunk_num):
        # grab the chunk from the dump path
        pass

class BlockWaiter(object):
    def __init__(self, steem_node):
        self.steem_node = steem_node
        self.db_api = self.steem_node.get_api("database_api")
        self.block_num_to_event = {}
        return

    async def start(self):
        await self.db_api.set_block_applied_callback( self.steem_node.cb(self.on_block) )

    async def on_block(self, block_header):
        block_num = int(block_header["previous"][:8], 16) + 1
        event = self.block_num_to_event.get(block_num)
        if event is not None:
            event.set()
            del self.block_num_to_event[block_num]
        return

    async def get_block(self, block_num, wait=True):
        while True:
            block = await self.db_api.get_block(block_num)
            if (block is not None) or (not wait):
                return block
            event = self.block_num_to_event.get(block_num)
            if event is None:
                event = tornado.locks.Event()
                self.block_num_to_event[block_num] = event
            await event.wait()

class BlockIterator(object):
    def __init__(self, steem_node, start_block, end_block):
        self.steem_node = steem_node
        self.waiter = BlockWaiter(self.steem_node)
        self.start_block = start_block
        self.end_block = end_block
        self.current_block = start_block
        self.started_waiter = False
        return

    @asyncutil.aiter_compat
    def __aiter__(self):
        return self

    async def __anext__(self):
        if (self.end_block != -1) and (self.current_block >= self.end_block):
            raise StopAsyncIteration
        if not self.started_waiter:
            await self.waiter.start()
            self.started_waiter = True
        block = await self.waiter.get_block(self.current_block)
        self.current_block += 1
        return block

async def main(argv, io_loop=None):
    parser = argparse.ArgumentParser(description="Watch Steem blocks on stdout")
    parser.add_argument("-s", "--server", dest="server", metavar="WEBSOCKET_URL", help="Specify API server")
    parser.add_argument("-b", "--blocks", dest="blocks", action="store_true", help="Watch full blocks")
    parser.add_argument("-t", "--tx", dest="tx", action="store_true", help="Watch transactions")
    parser.add_argument("-H", "--headers", dest="headers", action="store_true", help="Watch block headers")
    parser.add_argument("-o", "--ops", dest="ops", action="store_true", help="Watch operations")
    parser.add_argument("-r", "--range", dest="ranges", metavar="RANGE", action="append", help="Specify range start:end")
    parser.add_argument("-f", "--filter", dest="filters", metavar="FILT", action="append", help="Specify filter")
    #parser.add_argument("-d", "--dump", dest="dump", metavar="DUMP_DIR", help="Create blockchain dump files")
    #parser.add_argument("-l", "--load", dest="load", metavar="DUMP_DIR", help="Load blockchain dump files")

    args = parser.parse_args(argv[1:])

    node = steem_api.ApiNode(io_loop=io_loop, websocket_url=args.server)
    node.start()
    await node.wait_for_connection()

    db_api = node.get_api("database_api")
    dgpo = await db_api.get_dynamic_global_properties()
    head_block_num = dgpo["head_block_number"]

    for r in args.ranges:
        start_block, end_block = parse_range(head_block_num, r)
        async for block in BlockIterator(node, start_block, end_block):
            block_num = int(block["previous"][:8], 16) + 1
            if args.blocks:
                print(json.dumps(block, separators=(",", ":"), sort_keys=True))
            if args.headers:
                header = dict(block)
                del header["transactions"]
                print(json.dumps(header, separators=(",", ":"), sort_keys=True))
            if args.tx:
                for tx_num, tx in enumerate(block["transactions"]):
                    tx2 = dict(tx)
                    tx2["block_num"] = block_num
                    tx2["tx_num"] = tx_num
                    print(json.dumps(tx2, separators=(",", ":"), sort_keys=True))
            if args.ops:
                for tx_num, tx in enumerate(block["transactions"]):
                    for op_num, op in enumerate(tx["operations"]):
                        op2 = dict(op=op, block_num=block_num, tx_num=tx_num, op_num=op_num)
                        print(json.dumps(op2, separators=(",", ":"), sort_keys=True))

def sys_main():
    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.run_sync(lambda : main(sys.argv, io_loop=io_loop))

if __name__ == "__main__":
    sys_main()


import argparse
import json

from . import block_iterator
from . import steem_api

import tornado

import sys

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
        start_block, end_block = block_iterator.parse_range(head_block_num, r)
        async for block in block_iterator.BlockIterator(node, start_block, end_block):
            block_num = int(block["block"]["previous"][:8], 16) + 1
            if args.blocks:
                print(json.dumps(block, separators=(",", ":"), sort_keys=True))
            if args.headers:
                header = dict(block["block"])
                del header["transactions"]
                header_info = dict(block=header, info=block["info"])
                print(json.dumps(header_info, separators=(",", ":"), sort_keys=True))
            if args.tx:
                for tx_num, tx in enumerate(block["block"]["transactions"]):
                    tx2 = dict(tx)
                    tx2["block_num"] = block_num
                    tx2["tx_num"] = tx_num
                    print(json.dumps(tx2, separators=(",", ":"), sort_keys=True))
            if args.ops:
                for tx_num, tx in enumerate(block["block"]["transactions"]):
                    for op_num, op in enumerate(tx["operations"]):
                        op2 = dict(op=op, block_num=block_num, tx_num=tx_num, op_num=op_num)
                        print(json.dumps(op2, separators=(",", ":"), sort_keys=True))

def sys_main():
    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.run_sync(lambda : main(sys.argv, io_loop=io_loop))

if __name__ == "__main__":
    sys_main()

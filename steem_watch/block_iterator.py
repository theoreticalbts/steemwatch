
import tornado

from . import asyncutil

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
        self.block_info_api = self.steem_node.get_api("block_info_api")
        self.chunk_size = 10000
        self.current_chunk_start = -1
        self.current_chunk = []
        return

    @asyncutil.aiter_compat
    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            if (self.end_block != -1) and (self.current_block >= self.end_block):
                 raise StopAsyncIteration
            if (self.current_chunk_start > 0) and (self.current_block - self.current_chunk_start < len(self.current_chunk)):
                block_num = self.current_block
                self.current_block += 1
                return self.current_chunk[block_num - self.current_chunk_start]
            self.current_chunk = await self.block_info_api.get_blocks_with_info(start_block_num=self.current_block, count=self.chunk_size)
            self.current_chunk_start = self.current_block
            if not self.started_waiter:
                await self.waiter.start()
                self.started_waiter = True
            await self.waiter.get_block(self.current_block)
        return block

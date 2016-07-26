
from . import asyncutil

class HistoryIterator(object):
    def __init__(self, steem_node, account_name):
        self.steem_node = steem_node
        self.account_name = account_name
        self.current_op = 0
        self.db_api = self.steem_node.get_api("database_api")
        self.chunk_size = 2000
        self.current_chunk_start = -1
        self.current_chunk = {}
        return

    @asyncutil.aiter_compat
    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            result = self.current_chunk.get(self.current_op)
            if result is not None:
                self.current_op += 1
                return result
            api_result = await self.db_api.get_account_history(self.account_name, self.current_op + self.chunk_size-1, self.chunk_size-1)
            self.current_chunk = {k : v for k, v in api_result}
            if max(self.current_chunk.keys()) < self.current_op:
                raise StopAsyncIteration

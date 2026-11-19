"""Fictional JobsDB V7 responses and nonblocking cancellation for offline tests."""


class ImmediateEvent:
    def __init__(self): self.stopped = False
    def wait(self, seconds): return self.stopped
    def is_set(self): return self.stopped
    def set(self): self.stopped = True


def search(ids=(), page=1, size=30, count=None, token='fictional-token', since=1234):
    return {'data': {'jobSearchV7': {
        'results': {'jobs': [{'id': str(jid)} for jid in ids],
                    'pagination': {'page': page, 'pageSize': size,
                                   'resultCount': len(ids) if count is None else count}},
        'context': {'searchToken': token, 'filterNewSince': since}}}}

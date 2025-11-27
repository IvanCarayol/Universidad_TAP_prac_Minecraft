class MessageBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, msg_type, callback):
        if msg_type not in self.subscribers:
            self.subscribers[msg_type] = []
        self.subscribers[msg_type].append(callback)

    async def publish(self, msg):
        subscribers = self.subscribers.get(msg["type"], []) + self.subscribers.get("*", [])
        for cb in subscribers:
            await cb(msg)

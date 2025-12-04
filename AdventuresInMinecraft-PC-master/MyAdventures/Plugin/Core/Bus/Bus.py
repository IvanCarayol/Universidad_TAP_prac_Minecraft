class MessageBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, msg_type, callback):
        if msg_type not in self.subscribers:
            self.subscribers[msg_type] = []
        self.subscribers[msg_type].append(callback)

    def subscribe(self, msg_type, callback):
        if msg_type not in self.subscribers:
            self.subscribers[msg_type] = []
        self.subscribers[msg_type].append(callback)

    def unsubscribe(self, msg_type: str, callback):
        if msg_type in self.subscribers:
            try:
                self.subscribers[msg_type].remove(callback)
                if not self.subscribers[msg_type]:
                    del self.subscribers[msg_type]
            except ValueError:
                pass  

    async def publish(self, msg):
        subscribers = self.subscribers.get(msg["type"], []) + self.subscribers.get("*", [])
        for cb in subscribers:
            await cb(msg)

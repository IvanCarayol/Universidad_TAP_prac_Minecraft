class ExplorerBot():
    def init(self, agent_id, bus, mc):
        super().init(agent_id, bus)
        self.mc = mc
        self.center = (0, 0)  # referencia independiente del jugador

    async def perceive(self):
        x0, z0 = self.center
        height = self.mc.getHeight(x0 + 2, z0 + 2)
        return {"height": height}
        
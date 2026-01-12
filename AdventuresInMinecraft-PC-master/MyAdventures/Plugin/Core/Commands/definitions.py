from .command_system import CommandSystem

# Instancia que gestiona todo
cmd_manager = CommandSystem()

# Helper para no repetir código de envío
async def _send(bot, sender_id, topic, params):
    msg = {
        "type": topic,
        "source": f"player:{sender_id}",
        "target": bot.agent_id,
        "payload": params
    }
    await bot.bus.publish(msg)
    return f"[{bot.agent_id}] Comando enviado: {topic}"

# ============================
#         EXPLORER
# ============================
@cmd_manager.on("explorer start", "command.explorer.start.v1", target_bot="explorer")
async def explorer_start(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("explorer set", "command.explorer.set.v1", target_bot="explorer")
async def explorer_set(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("explorer stop", "command.explorer.stop.v1", target_bot="explorer")
async def explorer_stop(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("explorer pause", "command.explorer.pause.v1", target_bot="explorer")
async def explorer_pause(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("explorer resume", "command.explorer.resume.v1", target_bot="explorer")
async def explorer_resume(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("explorer status", "command.explorer.status.v1", target_bot="explorer")
async def explorer_status(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

# ============================
#         BUILDER
# ============================
@cmd_manager.on("builder start", "command.builder.start.v1", target_bot="builder")
async def builder_start(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder stop", "command.builder.stop.v1", target_bot="builder")
async def builder_stop(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder pause", "command.builder.pause.v1", target_bot="builder")
async def builder_pause(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder resume", "command.builder.resume.v1", target_bot="builder")
async def builder_resume(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder plan set", "command.builder.set.v1", target_bot="builder")
async def builder_set(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder plan list", "command.builder.list.v1", target_bot="builder")
async def builder_list(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("builder status", "command.builder.status.v1", target_bot="builder")
async def builder_status(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

# ============================
#         MINER
# ============================
@cmd_manager.on("miner start", "command.miner.start.v1", target_bot="miner")
async def miner_start(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("miner stop", "command.miner.stop.v1", target_bot="miner")
async def miner_stop(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("miner pause", "command.miner.pause.v1", target_bot="miner")
async def miner_pause(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("miner resume", "command.miner.resume.v1", target_bot="miner")
async def miner_resume(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("miner set", "command.miner.set.v1", target_bot="miner")
async def miner_set(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("miner status", "command.miner.status.v1", target_bot="miner")
async def miner_status(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

# ============================
#       WORLDSTATE
# ============================
@cmd_manager.on("worldstate start", "command.worldstate.start.v1", target_bot="worldstate")
async def worldstate_start(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)

@cmd_manager.on("worldstate status", "command.worldstate.status.v1", target_bot="worldstate")
async def worldstate_status(bot, params, sender_id, topic):
    return await _send(bot, sender_id, topic, params)
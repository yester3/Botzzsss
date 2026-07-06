"""
Almacenamiento simple basado en JSON.
Guarda, por servidor (guild):
- prefix: prefijo personalizado
- staff_role: ID del rol de staff (si no es admin)
- ticket_category: ID de la categoría donde se crean los tickets
- ticket_log_channel: canal para logs de tickets
- open_tickets: {user_id: {channel_id, opened_at_timestamp}}
- warns: {user_id: [ {reason, moderator, date}, ... ]}
- log_channels: {
    "kicks": channel_id,
    "bans": channel_id,
    "warns": channel_id,
    "mutes": channel_id,
    "locks": channel_id,
    "all": channel_id (si está puesto, todos van aquí)
  }
- inactivity_timeout: segundos después del cual cerrar un ticket sin mensajes (default 172800 = 48h)
"""

import json
import os
import threading
import datetime
import time

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
_lock = threading.Lock()


def _load():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_data(guild_id) -> dict:
    data = _load()
    return data.get(str(guild_id), {})


def set_guild_data(guild_id, guild_data: dict):
    with _lock:
        data = _load()
        data[str(guild_id)] = guild_data
        _save(data)


def update_guild_data(guild_id, **kwargs):
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid not in data:
            data[gid] = {}
        data[gid].update(kwargs)
        _save(data)


# ---------------- PREFIJO ----------------

def get_prefix(guild_id) -> str:
    return get_guild_data(guild_id).get("prefix", "!")


def set_prefix(guild_id, prefix: str):
    update_guild_data(guild_id, prefix=prefix)


# ---------------- WARNS ----------------

def add_warn(guild_id, user_id, reason: str, moderator_id):
    with _lock:
        data = _load()
        gid = str(guild_id)
        data.setdefault(gid, {})
        data[gid].setdefault("warns", {})
        data[gid]["warns"].setdefault(str(user_id), [])
        data[gid]["warns"][str(user_id)].append({
            "reason": reason,
            "moderator": moderator_id,
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        })
        _save(data)


def get_warns(guild_id, user_id) -> list:
    gdata = get_guild_data(guild_id)
    return gdata.get("warns", {}).get(str(user_id), [])


def clear_warns(guild_id, user_id):
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid in data and "warns" in data[gid] and str(user_id) in data[gid]["warns"]:
            del data[gid]["warns"][str(user_id)]
            _save(data)


# ---------------- TICKETS ----------------

def get_ticket_category(guild_id):
    return get_guild_data(guild_id).get("ticket_category")


def set_ticket_category(guild_id, category_id):
    update_guild_data(guild_id, ticket_category=category_id)


def get_open_tickets(guild_id) -> dict:
    """Retorna {user_id: {channel_id, opened_at}}"""
    return get_guild_data(guild_id).get("open_tickets", {})


def get_open_ticket_channel_for_user(guild_id, user_id) -> int:
    """Retorna el channel_id del ticket abierto del usuario, o None"""
    tickets = get_open_tickets(guild_id)
    ticket_data = tickets.get(str(user_id))
    if ticket_data:
        if isinstance(ticket_data, dict):
            return ticket_data.get("channel_id")
        else:
            return ticket_data  # formato antiguo (compatibilidad)
    return None


def add_open_ticket(guild_id, user_id, channel_id):
    with _lock:
        data = _load()
        gid = str(guild_id)
        data.setdefault(gid, {})
        data[gid].setdefault("open_tickets", {})
        data[gid]["open_tickets"][str(user_id)] = {
            "channel_id": channel_id,
            "opened_at": time.time()
        }
        _save(data)


def remove_open_ticket_by_channel(guild_id, channel_id):
    with _lock:
        data = _load()
        gid = str(guild_id)
        tickets = data.get(gid, {}).get("open_tickets", {})
        uid_to_remove = None
        for uid, ticket_data in tickets.items():
            cid = ticket_data if isinstance(ticket_data, int) else ticket_data.get("channel_id")
            if cid == channel_id:
                uid_to_remove = uid
                break
        if uid_to_remove:
            del tickets[uid_to_remove]
            data[gid]["open_tickets"] = tickets
            _save(data)


# ========== STAFF ROLE ==========

def get_staff_role(guild_id):
    return get_guild_data(guild_id).get("staff_role")


def set_staff_role(guild_id, role_id):
    update_guild_data(guild_id, staff_role=role_id)


# ========== LOG CHANNELS ==========

def get_log_channels(guild_id) -> dict:
    return get_guild_data(guild_id).get("log_channels", {})


def set_log_channel(guild_id, log_type: str, channel_id):
    """log_type puede ser: 'kicks', 'bans', 'warns', 'mutes', 'locks', 'tickets', 'all'"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        data.setdefault(gid, {})
        data[gid].setdefault("log_channels", {})
        data[gid]["log_channels"][log_type] = channel_id
        _save(data)


def get_log_channel(guild_id, log_type: str):
    """Obtiene el canal de log para un tipo. Si hay 'all', lo prioriza."""
    logs = get_log_channels(guild_id)
    if "all" in logs:
        return logs["all"]
    return logs.get(log_type)


# ========== INACTIVITY TIMEOUT ==========

def get_inactivity_timeout(guild_id) -> int:
    """Retorna segundos (default 48 horas = 172800)"""
    return get_guild_data(guild_id).get("inactivity_timeout", 172800)


def set_inactivity_timeout(guild_id, segundos: int):
    update_guild_data(guild_id, inactivity_timeout=segundos)


# ========== GIVEAWAYS ==========

def create_giveaway(guild_id, giveaway_id: str, giveaway_data: dict):
    """Guarda un giveaway con su ID (timestamp+random)"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        data.setdefault(gid, {})
        data[gid].setdefault("giveaways", {})
        data[gid]["giveaways"][giveaway_id] = giveaway_data
        _save(data)


def get_giveaway(guild_id, giveaway_id: str):
    """Obtiene un giveaway específico"""
    giveaways = get_guild_data(guild_id).get("giveaways", {})
    return giveaways.get(giveaway_id)


def get_all_giveaways(guild_id):
    """Obtiene todos los giveaways del servidor"""
    return get_guild_data(guild_id).get("giveaways", {})


def delete_giveaway(guild_id, giveaway_id: str):
    """Elimina un giveaway"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid in data and "giveaways" in data[gid]:
            data[gid]["giveaways"].pop(giveaway_id, None)
            _save(data)


def add_giveaway_participant(guild_id, giveaway_id: str, user_id: int):
    """Agrega un participante al giveaway"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid in data and "giveaways" in data[gid] and giveaway_id in data[gid]["giveaways"]:
            data[gid]["giveaways"][giveaway_id].setdefault("participants", [])
            if user_id not in data[gid]["giveaways"][giveaway_id]["participants"]:
                data[gid]["giveaways"][giveaway_id]["participants"].append(user_id)
                _save(data)
                return True
        return False


# ========== REACTION ROLES ==========

def add_reaction_role(guild_id, message_id: int, emoji: str, role_id: int):
    """Agrega una reaction role"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        data.setdefault(gid, {})
        data[gid].setdefault("reaction_roles", {})
        data[gid]["reaction_roles"].setdefault(str(message_id), {})
        data[gid]["reaction_roles"][str(message_id)][emoji] = role_id
        _save(data)


def get_reaction_roles(guild_id, message_id: int):
    """Obtiene todas las reaction roles de un mensaje"""
    rr = get_guild_data(guild_id).get("reaction_roles", {})
    return rr.get(str(message_id), {})


def remove_reaction_role(guild_id, message_id: int, emoji: str = None):
    """Elimina una reaction role específica o todas de un mensaje"""
    with _lock:
        data = _load()
        gid = str(guild_id)
        if gid in data and "reaction_roles" in data[gid]:
            msg_id_str = str(message_id)
            if emoji:
                data[gid]["reaction_roles"][msg_id_str].pop(emoji, None)
            else:
                data[gid]["reaction_roles"].pop(msg_id_str, None)
            _save(data)


# ========== WELCOMES & LEAVES ==========

def set_welcome_config(guild_id, config: dict):
    """Guarda configuración de bienvenida"""
    update_guild_data(guild_id, welcome_config=config)


def get_welcome_config(guild_id) -> dict:
    """Obtiene configuración de bienvenida"""
    return get_guild_data(guild_id).get("welcome_config", {})


def set_leave_config(guild_id, config: dict):
    """Guarda configuración de despedida"""
    update_guild_data(guild_id, leave_config=config)


def get_leave_config(guild_id) -> dict:
    """Obtiene configuración de despedida"""
    return get_guild_data(guild_id).get("leave_config", {})


# ========== AUTOROLE ==========

def set_autorole(guild_id, role_id):
    """Guarda el rol que se asigna automáticamente a nuevos miembros"""
    update_guild_data(guild_id, autorole=role_id)


def get_autorole(guild_id):
    """Obtiene el ID del autorole, o None si no está configurado"""
    return get_guild_data(guild_id).get("autorole")


# ========== SNIPE ==========

def set_snipe_channel(guild_id, channel_id):
    """Guarda el canal donde se envían mensajes eliminados automáticamente"""
    update_guild_data(guild_id, snipe_channel=channel_id)


def get_snipe_channel(guild_id):
    """Obtiene el ID del canal de snipe, o None si no está configurado"""
    return get_guild_data(guild_id).get("snipe_channel")

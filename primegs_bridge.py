#!/usr/bin/env python3
"""
primegs_bridge.py — мост prime.gs -> AxelChat.

Опрашивает чат prime.gs (REST, поле since_id) и переливает новые сообщения в
локальный API AxelChat (POST /api/v1/receive-events, появился в AxelChat 0.44.0).

AxelChat нативно prime.gs не поддерживает, но его HTTP-эндпоинт receive-events
предназначен ровно для сторонних интеграций. Исходники AxelChat трогать не нужно.

Зависимостей нет — только стандартная библиотека Python 3.

Запуск (рядом с работающим AxelChat):
    python primegs_bridge.py 257

где 257 — id чата из URL https://prime.gs/chat/257/messages

chat_id и прочие параметры можно один раз прописать в primegs_bridge.json рядом
со скриптом, тогда запуск сокращается до:
    python primegs_bridge.py
Аргументы командной строки, если переданы, перекрывают значения из конфига.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# Папка, рядом с которой лежит конфиг. В собранном .exe (PyInstaller) __file__
# указывает во временную распаковку, поэтому берём папку самого .exe через
# sys.executable. В обычном запуске — папку скрипта.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Конфиг-файл рядом с программой: можно один раз прописать chat_id и параметры,
# чтобы не передавать их в командной строке. Аргументы CLI перекрывают конфиг.
CONFIG_FILE = os.path.join(APP_DIR, "primegs_bridge.json")

DEFAULTS = {
    "chat_id": None,
    "axel_url": "http://127.0.0.1:8356",
    "interval": 2.0,
    "period": "current_stream",
    "limit": 50,
    "backfill": False,
}

# serviceId "primegs" нет в списке известных платформ AxelChat, поэтому это
# кастомный идентификатор. Чтобы у сообщений отображался значок платформы,
# обязательно задаём serviceBadge — URL иконки prime.gs.
SERVICE_ID = "primegs"
SERVICE_BADGE = "https://prime.gs/favicon.ico"

PRIMEGS_BASE = "https://prime.gs"


def log(*args):
    print(time.strftime("[%H:%M:%S]"), *args, flush=True)


def write_config_template():
    """Создать шаблон конфига рядом с программой, если его ещё нет."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, ensure_ascii=False, indent=4)
        log(f"Создан шаблон конфига: {CONFIG_FILE} — впишите в него \"chat_id\".")
    except OSError as e:
        log(f"Не удалось создать шаблон конфига {CONFIG_FILE}: {e}")


def load_config():
    """Прочитать primegs_bridge.json, если он есть. Неизвестные ключи игнорируются."""
    if not os.path.exists(CONFIG_FILE):
        write_config_template()
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            log(f"Конфиг {CONFIG_FILE} игнорируется: ожидался объект JSON.")
            return {}
        return {k: cfg[k] for k in DEFAULTS if k in cfg}
    except (OSError, ValueError) as e:
        log(f"Не удалось прочитать конфиг {CONFIG_FILE}: {e}. Использую CLI/умолчания.")
        return {}


def http_get_json(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "primegs-axelchat-bridge/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def http_post_json(url, payload, timeout=20):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "primegs-axelchat-bridge/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def convert_published_at(created_at):
    """ISO 8601 prime.gs ('2026-06-04T16:50:43+00:00') -> формат AxelChat
    'YYYY-MM-DDTHH:MM:SS.mmm' без таймзоны."""
    if not created_at:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000")
    try:
        # Python <3.11 не понимает 'Z'; на всякий случай нормализуем.
        normalized = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    except ValueError:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000")


def build_event(msg, chat_id):
    """Сообщение prime.gs -> событие receive-events AxelChat."""
    user = msg.get("user") or {}
    user_id = user.get("id")
    name = user.get("nickname") or user.get("name") or "anon"

    right_tags = []
    for badge in user.get("badges") or []:
        label = badge.get("label")
        if label:
            right_tags.append({"text": label})

    text = msg.get("text", "")
    content = {"type": "text", "data": {"text": text}}
    if msg.get("is_action"):
        content["style"] = {"font-style": "italic"}

    author = {
        "id": f"{SERVICE_ID}_{user_id}",
        "name": name,
        "serviceId": SERVICE_ID,
        "serviceBadge": SERVICE_BADGE,
    }
    color = user.get("chat_color")
    if color:
        author["color"] = color
    if right_tags:
        author["rightTags"] = right_tags

    event = {
        "id": f"{SERVICE_ID}_{chat_id}_{msg.get('id')}",
        "eventType": "Message",
        "edited": False,
        "deletedOnPlatform": bool(msg.get("is_deleted")),
        "markedAsDeleted": bool(msg.get("is_deleted")),
        "publishedAt": convert_published_at(msg.get("created_at")),
        "author": author,
        "contents": [content],
    }
    return event


def fetch_messages(chat_id, period, since_id, limit):
    url = f"{PRIMEGS_BASE}/chat/{chat_id}/messages?period={period}&limit={limit}"
    if since_id is not None:
        url += f"&since_id={since_id}"
    return http_get_json(url)


def drain(chat_id, period, since_id, limit, max_pages=20):
    """Считать все доступные сообщения новее since_id, разбирая пагинацию
    has_more. Возвращает (messages, new_since_id)."""
    collected = []
    pages = 0
    while pages < max_pages:
        pages += 1
        data = fetch_messages(chat_id, period, since_id, limit)
        batch = data.get("messages") or []
        if batch:
            collected.extend(batch)
            since_id = max(m.get("id", since_id) for m in batch)
        if not data.get("has_more"):
            break
        if not batch:
            break
    return collected, since_id


def send_to_axelchat(axel_url, events):
    url = axel_url.rstrip("/") + "/api/v1/receive-events"
    resp = http_post_json(url, events)
    return resp


def main():
    # Слои настроек: умолчания <- конфиг-файл <- аргументы командной строки.
    cfg = dict(DEFAULTS)
    cfg.update(load_config())

    parser = argparse.ArgumentParser(
        description="Мост prime.gs -> AxelChat (опрос чата и пересылка в receive-events). "
                    f"Параметры можно задать в конфиге {os.path.basename(CONFIG_FILE)}."
    )
    # chat_id необязателен в CLI, если он задан в конфиге. default=None, чтобы
    # отличить «не передан» от переданного значения.
    parser.add_argument("chat_id", nargs="?", default=None,
                        help="id чата prime.gs, напр. 257 (можно задать в конфиге)")
    parser.add_argument("--axel-url", default=None,
                        help=f"базовый URL AxelChat (по умолчанию {cfg['axel_url']})")
    parser.add_argument("--interval", type=float, default=None,
                        help=f"пауза между опросами, сек (по умолчанию {cfg['interval']})")
    parser.add_argument("--period", default=None,
                        help=f"параметр period (по умолчанию {cfg['period']})")
    parser.add_argument("--limit", type=int, default=None,
                        help=f"limit на запрос (по умолчанию {cfg['limit']})")
    parser.add_argument("--backfill", action="store_true", default=None,
                        help="отправить и стартовую пачку уже существующих сообщений")
    parsed = parser.parse_args()

    # CLI перекрывает конфиг только там, где значение реально передано.
    for key in ("chat_id", "axel_url", "interval", "period", "limit", "backfill"):
        value = getattr(parsed, key)
        if value is not None:
            cfg[key] = value

    if not cfg["chat_id"]:
        parser.error(
            f"не задан chat_id: укажите его аргументом (python {os.path.basename(sys.argv[0])} 257) "
            f"или ключом \"chat_id\" в {CONFIG_FILE}"
        )

    args = argparse.Namespace(**cfg)
    chat_id = str(args.chat_id)
    log(f"Старт моста. chat_id={chat_id} period={args.period} "
        f"-> AxelChat {args.axel_url} (interval={args.interval}s)")

    # Стартовый baseline: берём текущие сообщения, чтобы не вываливать историю.
    since_id = None
    try:
        initial = fetch_messages(chat_id, args.period, None, args.limit)
        msgs = initial.get("messages") or []
        if msgs:
            since_id = max(m.get("id", 0) for m in msgs)
        log(f"Старт с since_id={since_id} (сообщений в начале: {len(msgs)})")
        if args.backfill and msgs:
            _push(args.axel_url, [build_event(m, chat_id) for m in msgs])
    except urllib.error.URLError as e:
        log(f"Не удалось получить стартовую пачку с prime.gs: {e}. Стартуем с since_id=None.")

    while True:
        try:
            new_msgs, since_id = drain(chat_id, args.period, since_id, args.limit)
            if new_msgs:
                events = [build_event(m, chat_id) for m in new_msgs]
                _push(args.axel_url, events)
        except urllib.error.URLError as e:
            # AxelChat не запущен (Connection refused) или сеть недоступна —
            # логируем и продолжаем, не падаем.
            log(f"Ошибка сети/соединения: {e}")
        except Exception as e:  # noqa: BLE001 — мост должен пережить любую ошибку
            log(f"Непредвиденная ошибка: {e!r}")
        time.sleep(args.interval)


def _push(axel_url, events):
    if not events:
        return
    try:
        resp = send_to_axelchat(axel_url, events)
        added = len(resp.get("addedMessages", [])) if isinstance(resp, dict) else "?"
        log(f"Отправлено {len(events)} событ., AxelChat принял добавленных: {added}")
    except urllib.error.URLError as e:
        log(f"AxelChat недоступен ({e}). Сообщения этой итерации потеряны "
            f"(будут пропущены, since_id уже сдвинут).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Остановлено пользователем.")
        sys.exit(0)

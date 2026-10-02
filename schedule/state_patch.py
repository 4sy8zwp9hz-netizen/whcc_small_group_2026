"""Small wire mutations; materialized compatibility state remains in memory only."""
import copy
import re
from datetime import datetime
from .data import DataError


def entities(items):
    records, profiles, responses = {}, {}, {}
    def profile(value):
        value = {key: copy.deepcopy(value[key]) for key in ("id", "name", "members")}
        previous = profiles.get(value["id"])
        if previous is not None and previous != value:
            raise DataError("Backend household names or member IDs are inconsistent.")
        profiles[value["id"]] = value
    for item in items:
        record = item["record"]
        records[record["id"]] = copy.deepcopy(record)
        for value in item.get("households", []):
            profile(value)
        for reply in item["responses"]:
            profile(reply)
            responses[(record["id"], reply["id"])] = {
                "meeting": record["id"], "id": reply["id"],
                "attending": copy.deepcopy(reply["attending"]), "updated_at": reply["updated_at"]}
    return records, profiles, responses


def materialize(records, profiles, responses):
    result = []
    for record in sorted(records.values(), key=lambda r: (r["values"]["date"], r["values"]["time"], r["id"])):
        replies = []
        for (meeting, identity), response in sorted(responses.items()):
            if meeting == record["id"]:
                if identity not in profiles:
                    raise DataError("A backend response has no household profile.")
                replies.append({**copy.deepcopy(profiles[identity]),
                                "attending": response["attending"], "updated_at": response["updated_at"]})
        result.append({"record": copy.deepcopy(record), "responses": replies})
    if any(meeting not in records for meeting, _ in responses):
        raise DataError("A backend response has no meeting.")
    if result:
        result[0]["households"] = [copy.deepcopy(profiles[key]) for key in sorted(profiles)]
    elif profiles:
        raise DataError("Household profiles require at least one schedule record.")
    return result


def diff(base, desired):
    old_records, old_profiles, old_responses = entities(base)
    records, profiles, responses = entities(desired)
    if old_records.keys() - records.keys() or old_profiles.keys() - profiles.keys():
        raise DataError("Deleting meetings or household profiles is not supported.")
    return {"records": [records[key] for key in sorted(records) if old_records.get(key) != records[key]],
            "profiles": [profiles[key] for key in sorted(profiles) if old_profiles.get(key) != profiles[key]],
            "responses": [responses[key] for key in sorted(responses) if old_responses.get(key) != responses[key]],
            "cleared": [list(key) for key in sorted(old_responses.keys() - responses.keys())]}


def apply(base, patch):
    if not isinstance(patch, dict) or set(patch) != {"records", "profiles", "responses", "cleared"}:
        raise DataError("Invalid backend mutation fields.")
    if not all(isinstance(value, list) for value in patch.values()):
        raise DataError("Invalid backend mutation lists.")
    records, profiles, responses = entities(base)
    for values, key in ((patch["records"], lambda v: v["id"]),
                        (patch["profiles"], lambda v: v["id"]),
                        (patch["responses"], lambda v: (v["meeting"], v["id"])),
                        (patch["cleared"], lambda v: tuple(v))):
        identities = [key(value) for value in values]
        if len(set(identities)) != len(identities):
            raise DataError("Duplicate backend mutation identity.")
    for record in patch["records"]:
        records[record["id"]] = copy.deepcopy(record)
    for profile in patch["profiles"]:
        profiles[profile["id"]] = copy.deepcopy(profile)
    for response in patch["responses"]:
        if set(response) != {"meeting", "id", "attending", "updated_at"}:
            raise DataError("Invalid backend response mutation.")
        if (not re.fullmatch(r"[a-f0-9]{32}", response["meeting"])
                or not re.fullmatch(r"[a-f0-9]{64}", response["id"])
                or not isinstance(response["attending"], list)
                or len(set(response["attending"])) != len(response["attending"])):
            raise DataError("Invalid backend response identity or selection.")
        datetime.fromisoformat(response["updated_at"])
        responses[(response["meeting"], response["id"])] = copy.deepcopy(response)
    for key in patch["cleared"]:
        if not isinstance(key, list) or len(key) != 2 or not all(isinstance(value, str) for value in key):
            raise DataError("Invalid cleared backend response.")
        if not re.fullmatch(r"[a-f0-9]{32}", key[0]) or not re.fullmatch(r"[a-f0-9]{64}", key[1]):
            raise DataError("Invalid cleared response identity.")
        if tuple(key) in {(r["meeting"], r["id"]) for r in patch["responses"]}:
            raise DataError("A response cannot be changed and cleared in the same update.")
        responses.pop(tuple(key), None)
    return materialize(records, profiles, responses)

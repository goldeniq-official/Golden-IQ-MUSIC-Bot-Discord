# -*- coding: utf-8 -*-
"""Guild/user data reads must stay cached.

The audit assumed this data was re-read from MongoDB on every interaction.
It is not: BaseDB has held a TTLCache since before this work, get_data
consults it first, and update_data writes through. These tests exist to
keep that true — the caching is easy to drop by accident while refactoring
get_data, and losing it would put a database round trip on every button
press.
"""
from __future__ import annotations

import pytest

from utils.db import BaseDB, DBModel, MongoDatabase


class _FakeCollection:
    def __init__(self, store, counter):
        self._store = store
        self._counter = counter

    async def find_one(self, query):
        self._counter["reads"] += 1
        return self._store.get(query["_id"])

    async def update_one(self, query, update, upsert=False):
        self._store[query["_id"]] = dict(update["$set"], _id=query["_id"])


class _FakeConnect:
    def __init__(self):
        self.store = {}
        self.counter = {"reads": 0}

    def __getitem__(self, _collection):
        return {DBModel.guilds: _FakeCollection(self.store, self.counter)}


def _make_db():
    db = MongoDatabase.__new__(MongoDatabase)
    BaseDB.__init__(db)
    db._connect = _FakeConnect()
    return db


def test_base_db_has_a_bounded_ttl_cache():
    db = BaseDB.__new__(BaseDB)
    BaseDB.__init__(db)
    assert db.cache.maxsize > 0, "cache must be bounded"
    assert db.cache.ttl > 0, "cache must expire so out-of-band edits converge"


async def test_repeat_reads_hit_the_database_once():
    db = _make_db()
    model = {DBModel.guilds: {"ver": 1, "player_controller": {"skin": "default"}}}
    db._connect.store["3003"] = {"_id": "3003", "ver": 1,
                                 "player_controller": {"skin": "default"}}

    for _ in range(5):
        await db.get_data(3003, db_name=DBModel.guilds, collection="guilds",
                          default_model=model)

    assert db._connect.counter["reads"] == 1, (
        f"expected 1 database read, got {db._connect.counter['reads']} — "
        f"the cache is no longer being consulted"
    )


async def test_write_refreshes_the_cached_value():
    db = _make_db()
    model = {DBModel.guilds: {"ver": 1, "player_controller": {"skin": "default"}}}
    db._connect.store["3003"] = {"_id": "3003", "ver": 1,
                                 "player_controller": {"skin": "default"}}

    await db.get_data(3003, db_name=DBModel.guilds, collection="guilds",
                      default_model=model)
    await db.update_data("3003", {"ver": 1, "player_controller": {"skin": "mini"}},
                         db_name=DBModel.guilds, collection="guilds")
    result = await db.get_data(3003, db_name=DBModel.guilds, collection="guilds",
                               default_model=model)

    assert result["player_controller"]["skin"] == "mini", (
        "a write must not leave a stale value visible to the next read"
    )


async def test_distinct_guilds_are_cached_separately():
    db = _make_db()
    model = {DBModel.guilds: {"ver": 1, "player_controller": {"skin": "default"}}}
    db._connect.store["3003"] = {"_id": "3003", "ver": 1,
                                 "player_controller": {"skin": "lite"}}
    db._connect.store["4004"] = {"_id": "4004", "ver": 1,
                                 "player_controller": {"skin": "mini"}}

    a = await db.get_data(3003, db_name=DBModel.guilds, collection="guilds",
                          default_model=model)
    b = await db.get_data(4004, db_name=DBModel.guilds, collection="guilds",
                          default_model=model)

    assert a["player_controller"]["skin"] == "lite"
    assert b["player_controller"]["skin"] == "mini"
    assert db._connect.counter["reads"] == 2

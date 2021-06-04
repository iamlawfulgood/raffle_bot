import os
import sqlite3


class DB:

    __instance = None
    __instantiation_key = "YAY_SINGLETON_HACKS_IN_PYTHON"

    @classmethod
    def get(cls):
        if cls.__instance is None:
            cls.__instance = DB(instantiation_key=DB.__instantiation_key)
        return cls.__instance

    def __init__(self, instantiation_key=None):
        assert (
            instantiation_key == DB.__instantiation_key
        ), "Use DB.get() to connect to the database"
        self.conn = sqlite3.connect(os.environ.get("DB_PATH"))

    def create_raffle(self, guild_id, message_id):
        c = self.conn.cursor()
        if self.has_ongoing_raffle(guild_id):
            raise Exception("There is already an ongoing raffle!")

        c.execute(
            'INSERT INTO "raffles" (guild_id, message_id) VALUES (?, ?)',
            (
                guild_id,
                message_id,
            ),
        )
        self.conn.commit()
        c.close()

    def get_raffle_message_id(self, guild_id):
        c = self.conn.cursor()
        if not self.has_ongoing_raffle(guild_id):
            raise Exception("There is no ongoing raffle! You need to start a new one.")

        c.execute(
            'SELECT message_id FROM "raffles" WHERE "guild_id"=?',
            (guild_id,),
        )
        result = c.fetchone()
        if result is None:
            return None
        return result[0]

    def has_ongoing_raffle(self, guild_id):
        c = self.conn.cursor()
        c.execute('SELECT rowid FROM "raffles" WHERE "guild_id"=?', (guild_id,))
        result = c.fetchone()
        return result is not None

    def close_raffle(self, guild_id):
        c = self.conn.cursor()
        if not self.has_ongoing_raffle(guild_id):
            raise Exception("There is no ongoing raffle! You need to start a new one.")

        c.execute(
            'DELETE FROM "raffles" WHERE "guild_id"=?',
            (guild_id,),
        )
        self.conn.commit()
        c.close()

    def record_win(self, guild_id, message_id, *users):
        c = self.conn.cursor()
        values = list(map(lambda user: (guild_id, message_id, user.id), users))
        c.executemany(
            'INSERT INTO "past_wins" (guild_id, message_id, user_id) VALUES (?, ?, ?)',
            values,
        )
        self.conn.commit()
        c.close()

    def clear_wins(self, guild_id, message_id):
        c = self.conn.cursor()
        c.execute(
            'DELETE FROM "past_wins" WHERE guild_id = ? AND message_id = ?',
            (
                guild_id,
                message_id,
            ),
        )
        self.conn.commit()
        c.close()

    def recent_winners(self, guild_id):
        c = self.conn.cursor()
        c.execute(
            (
                'SELECT DISTINCT user_id FROM "past_wins" WHERE guild_id = ?'
                "ORDER BY id DESC LIMIT 5"
            ),
            (guild_id,),
        )
        results = c.fetchall()
        winners = []
        for result in results:
            winners.append(int(result[0]))
        return winners

    def all_winners(self, guild_id):
        c = self.conn.cursor()
        c.execute(
            'SELECT DISTINCT user_id FROM "past_wins" WHERE guild_id = ?',
            (guild_id,),
        )
        results = c.fetchall()
        winners = []
        for result in results:
            winners.append(int(result[0]))
        return winners

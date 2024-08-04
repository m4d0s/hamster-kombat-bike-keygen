BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "keys" (
	"id"	INTEGER DEFAULT 0,
	"tg_id"	INTEGER NOT NULL DEFAULT 0,
	"key"	INTEGER NOT NULL DEFAULT 'BIKE-TH1S-1S-JU5T-T35T',
	"time"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "users" (
	"id"	INTEGER NOT NULL DEFAULT 0,
	"sub1"	INTEGER NOT NULL DEFAULT 0
);
COMMIT;

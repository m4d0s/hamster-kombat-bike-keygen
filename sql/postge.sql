-- DROP SCHEMA "hamster-kombat-keys";

CREATE SCHEMA "hamster-kombat-keys" AUTHORIZATION postgres;

-- DROP SEQUENCE "hamster-kombat-keys".cache_id_seq;

CREATE SEQUENCE "hamster-kombat-keys".cache_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE "hamster-kombat-keys".keys_id_seq;

CREATE SEQUENCE "hamster-kombat-keys".keys_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE "hamster-kombat-keys".promo_id_seq;

CREATE SEQUENCE "hamster-kombat-keys".promo_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE "hamster-kombat-keys".users_id_seq;

CREATE SEQUENCE "hamster-kombat-keys".users_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;-- "hamster-kombat-keys".promo определение

-- Drop table

-- DROP TABLE "hamster-kombat-keys".promo;

CREATE TABLE "hamster-kombat-keys".promo (
	id int8 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE) NOT NULL,
	"name" text NOT NULL,
	"desc" text NOT NULL,
	link text NOT NULL,
	check_id int2 DEFAULT 0 NOT NULL,
	CONSTRAINT promo_pk PRIMARY KEY (id)
);


-- "hamster-kombat-keys".users определение

-- Drop table

-- DROP TABLE "hamster-kombat-keys".users;

CREATE TABLE "hamster-kombat-keys".users (
	id int8 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE) NOT NULL,
	tg_username text DEFAULT '-'::text NOT NULL,
	tg_id int8 DEFAULT 0 NOT NULL,
	ref_id int8 DEFAULT '-1'::integer NOT NULL,
	"right" int2 DEFAULT 0 NOT NULL,
	lang text DEFAULT 'en'::text NOT NULL,
	CONSTRAINT newtable_pk PRIMARY KEY (id),
	CONSTRAINT users_unique UNIQUE (tg_id)
);


-- "hamster-kombat-keys".cache определение

-- Drop table

-- DROP TABLE "hamster-kombat-keys".cache;

CREATE TABLE "hamster-kombat-keys".cache (
	id int8 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE) NOT NULL,
	user_id int8 NOT NULL,
	welcome int8 NULL,
	loading int8 NULL,
	report int8 NULL,
	process bool DEFAULT true NOT NULL,
	error int8 NULL,
	CONSTRAINT cache_pk PRIMARY KEY (id),
	CONSTRAINT cache_unique UNIQUE (user_id),
	CONSTRAINT cache_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- "hamster-kombat-keys"."keys" определение

-- Drop table

-- DROP TABLE "hamster-kombat-keys"."keys";

CREATE TABLE "hamster-kombat-keys"."keys" (
	id int8 GENERATED ALWAYS AS IDENTITY( INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE) NOT NULL,
	user_id int8 DEFAULT 0 NOT NULL,
	"key" text NOT NULL,
	"type" text DEFAULT 'KEY'::text NOT NULL,
	"time" int8 DEFAULT 0 NOT NULL,
	used bool DEFAULT true NOT NULL,
	CONSTRAINT keys_pk PRIMARY KEY (id),
	CONSTRAINT keys_unique UNIQUE (key),
	CONSTRAINT keys_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON DELETE CASCADE ON UPDATE CASCADE
);


-- "hamster-kombat-keys".subs определение

-- Drop table

-- DROP TABLE "hamster-kombat-keys".subs;

CREATE TABLE "hamster-kombat-keys".subs (
	id int8 NOT NULL,
	user_id int8 NOT NULL,
	promo_id int8 NULL,
	CONSTRAINT subs_pk PRIMARY KEY (id),
	CONSTRAINT subs_promo_fk FOREIGN KEY (promo_id) REFERENCES "hamster-kombat-keys".promo(id) ON DELETE CASCADE ON UPDATE CASCADE,
	CONSTRAINT subs_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON DELETE CASCADE ON UPDATE CASCADE
);
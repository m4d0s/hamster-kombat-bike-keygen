-- Создание схемы
CREATE SCHEMA "hamster-kombat-keys" AUTHORIZATION postgres;

-- Создание последовательностей
CREATE SEQUENCE "hamster-kombat-keys".keys_id_seq
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    START 1
    CACHE 1
    NO CYCLE;

CREATE SEQUENCE "hamster-kombat-keys".promo_id_seq
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    START 1
    CACHE 1
    NO CYCLE;

CREATE SEQUENCE "hamster-kombat-keys".users_id_seq
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 9223372036854775807
    START 1
    CACHE 1
    NO CYCLE;

-- Создание таблицы promo
CREATE TABLE "hamster-kombat-keys".promo (
    id int8 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE
    ) NOT NULL,
    "name" text NOT NULL,
    "desc" text NOT NULL,
    link text NOT NULL,
    check_id int2 DEFAULT 0 NOT NULL,
    CONSTRAINT promo_pk PRIMARY KEY (id),
    CONSTRAINT unique_promo_link UNIQUE (link)
);

-- Создание таблицы users
CREATE TABLE "hamster-kombat-keys".users (
    id int8 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE
    ) NOT NULL,
    tg_username text DEFAULT '-'::text NOT NULL,
    tg_id int8 DEFAULT 0 NOT NULL,
    ref_id int8 DEFAULT '-1'::integer NOT NULL,
    "right" int2 DEFAULT 0 NOT NULL,
    CONSTRAINT newtable_pk PRIMARY KEY (id),
    CONSTRAINT unique_tg_id UNIQUE (tg_id)
);

-- Создание таблицы keys
CREATE TABLE "hamster-kombat-keys"."keys" (
    id int8 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 1 CACHE 1 NO CYCLE
    ) NOT NULL,
    user_id int8 DEFAULT 0 NOT NULL,
    "key" text NOT NULL,
    "type" text DEFAULT 'KEY'::text NOT NULL,
    "time" int8 DEFAULT 0 NULL,
    CONSTRAINT keys_pk PRIMARY KEY (id),
    CONSTRAINT unique_key UNIQUE ("key"),
    CONSTRAINT keys_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Создание таблицы subs
CREATE TABLE "hamster-kombat-keys".subs (
    id int8 NOT NULL,
    user_id int8 NOT NULL,
    promo_id int8 NULL,
    CONSTRAINT subs_pk PRIMARY KEY (id),
    CONSTRAINT subs_promo_fk FOREIGN KEY (promo_id) REFERENCES "hamster-kombat-keys".promo(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT subs_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT unique_user_promo UNIQUE (user_id, promo_id)
);

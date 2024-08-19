--
-- PostgreSQL database cluster dump
--

-- Started on 2024-08-20 03:22:00

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS;

--
-- User Configurations
--






--
-- Databases
--

--
-- Database "template1" dump
--

\connect template1

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.3
-- Dumped by pg_dump version 16.3

-- Started on 2024-08-20 03:22:00

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- Completed on 2024-08-20 03:22:00

--
-- PostgreSQL database dump complete
--

--
-- Database "postgres" dump
--

\connect postgres

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.3
-- Dumped by pg_dump version 16.3

-- Started on 2024-08-20 03:22:00

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 8 (class 2615 OID 16633)
-- Name: config; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA config;


--
-- TOC entry 6 (class 2615 OID 16398)
-- Name: hamster-kombat-keys; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA "hamster-kombat-keys";


--
-- TOC entry 7 (class 2615 OID 16566)
-- Name: promotion; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA promotion;


--
-- TOC entry 2 (class 3079 OID 16384)
-- Name: adminpack; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS adminpack WITH SCHEMA pg_catalog;


--
-- TOC entry 4956 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION adminpack; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION adminpack IS 'administrative functions for PostgreSQL';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 230 (class 1259 OID 16641)
-- Name: number; Type: TABLE; Schema: config; Owner: -
--

CREATE TABLE config.number (
    key text NOT NULL,
    value bigint NOT NULL
);


--
-- TOC entry 232 (class 1259 OID 16649)
-- Name: proxy; Type: TABLE; Schema: config; Owner: -
--

CREATE TABLE config.proxy (
    id bigint NOT NULL,
    link character varying NOT NULL,
    work boolean DEFAULT false NOT NULL
);


--
-- TOC entry 231 (class 1259 OID 16648)
-- Name: proxy_id_seq; Type: SEQUENCE; Schema: config; Owner: -
--

ALTER TABLE config.proxy ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME config.proxy_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 229 (class 1259 OID 16634)
-- Name: text; Type: TABLE; Schema: config; Owner: -
--

CREATE TABLE config.text (
    key text NOT NULL,
    value text NOT NULL
);


--
-- TOC entry 223 (class 1259 OID 16478)
-- Name: cache; Type: TABLE; Schema: hamster-kombat-keys; Owner: -
--

CREATE TABLE "hamster-kombat-keys".cache (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    welcome bigint,
    loading bigint,
    report bigint,
    process boolean DEFAULT true NOT NULL,
    error bigint,
    tasks bigint DEFAULT 0 NOT NULL,
    addtask bigint,
    deletetask bigint
);


--
-- TOC entry 222 (class 1259 OID 16477)
-- Name: cashe_id_seq; Type: SEQUENCE; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE "hamster-kombat-keys".cache ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".cashe_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 221 (class 1259 OID 16451)
-- Name: keys; Type: TABLE; Schema: hamster-kombat-keys; Owner: -
--

CREATE TABLE "hamster-kombat-keys".keys (
    id bigint NOT NULL,
    user_id bigint DEFAULT 0 NOT NULL,
    key text NOT NULL,
    type text DEFAULT 'KEY'::text NOT NULL,
    "time" bigint DEFAULT 0 NOT NULL,
    used boolean DEFAULT true NOT NULL,
    game_id smallint DEFAULT 1
);


--
-- TOC entry 220 (class 1259 OID 16450)
-- Name: keys_id_seq; Type: SEQUENCE; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE "hamster-kombat-keys".keys ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".keys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 219 (class 1259 OID 16400)
-- Name: users; Type: TABLE; Schema: hamster-kombat-keys; Owner: -
--

CREATE TABLE "hamster-kombat-keys".users (
    id bigint NOT NULL,
    tg_username text DEFAULT '-'::text NOT NULL,
    tg_id bigint DEFAULT 0 NOT NULL,
    ref_id bigint DEFAULT '-1'::integer NOT NULL,
    "right" smallint DEFAULT 0 NOT NULL,
    lang text DEFAULT 'en'::text NOT NULL
);


--
-- TOC entry 218 (class 1259 OID 16399)
-- Name: users_id_seq; Type: SEQUENCE; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE "hamster-kombat-keys".users ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 226 (class 1259 OID 16577)
-- Name: checker; Type: TABLE; Schema: promotion; Owner: -
--

CREATE TABLE promotion.checker (
    id bigint NOT NULL,
    promo_id bigint NOT NULL,
    user_id bigint NOT NULL
);


--
-- TOC entry 225 (class 1259 OID 16572)
-- Name: games; Type: TABLE; Schema: promotion; Owner: -
--

CREATE TABLE promotion.games (
    id smallint NOT NULL,
    name text NOT NULL,
    "desc" text NOT NULL,
    link text NOT NULL
);


--
-- TOC entry 228 (class 1259 OID 16582)
-- Name: promo_translate; Type: TABLE; Schema: promotion; Owner: -
--

CREATE TABLE promotion.promo_translate (
    id bigint NOT NULL,
    lang text NOT NULL,
    type text NOT NULL,
    value text NOT NULL,
    promo_id bigint NOT NULL
);


--
-- TOC entry 227 (class 1259 OID 16581)
-- Name: newtable_id_seq; Type: SEQUENCE; Schema: promotion; Owner: -
--

ALTER TABLE promotion.promo_translate ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME promotion.newtable_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 224 (class 1259 OID 16567)
-- Name: promo; Type: TABLE; Schema: promotion; Owner: -
--

CREATE TABLE promotion.promo (
    name text NOT NULL,
    "desc" text NOT NULL,
    link text NOT NULL,
    check_id bigint NOT NULL,
    control bigint NOT NULL,
    type text DEFAULT 'task'::text NOT NULL,
    id bigint NOT NULL
);


--
-- TOC entry 235 (class 1259 OID 16686)
-- Name: promo_id_seq; Type: SEQUENCE; Schema: promotion; Owner: -
--

ALTER TABLE promotion.promo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME promotion.promo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 234 (class 1259 OID 16660)
-- Name: promo_prizes; Type: TABLE; Schema: promotion; Owner: -
--

CREATE TABLE promotion.promo_prizes (
    id bigint NOT NULL,
    promo_id bigint NOT NULL,
    name text NOT NULL,
    winner_id bigint DEFAULT 0 NOT NULL,
    owner_id bigint DEFAULT 0 NOT NULL
);


--
-- TOC entry 233 (class 1259 OID 16659)
-- Name: promo_prizes_id_seq; Type: SEQUENCE; Schema: promotion; Owner: -
--

ALTER TABLE promotion.promo_prizes ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME promotion.promo_prizes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 4945 (class 0 OID 16641)
-- Dependencies: 230
-- Data for Name: number; Type: TABLE DATA; Schema: config; Owner: -
--

COPY config.number (key, value) FROM stdin;
gen_proxy	10
debug_delay	10000
dev_id	5043492422
delay	30
max_retry	10
count	16
main_group	-1002217574534
main_channel	-1002208722522
\.


--
-- TOC entry 4947 (class 0 OID 16649)
-- Dependencies: 232
-- Data for Name: proxy; Type: TABLE DATA; Schema: config; Owner: -
--

COPY config.proxy (id, link, work) FROM stdin;
1	http://leucois9ux-mobile-country-GB-state-6269131-city-2644210-hold-session-session-669150dcb2dc8:eThapYQvdMX5Tttn@93.190.138.107:9999	f
2	http://leucois9ux-mobile-country-GB-state-6269131-city-2641673-hold-session-session-669150ea5b3ca:eThapYQvdMX5Tttn@93.190.138.107:9999	f
3	http://leucois9ux-mobile-country-GB-state-6269131-city-2641170-hold-session-session-66915103a5803:eThapYQvdMX5Tttn@93.190.138.107:9999	f
4	http://leucois9ux-mobile-country-GB-state-6269131-city-2644210-hold-session-session-669150dcb2dc8:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
5	http://leucois9ux-mobile-country-GB-state-6269131-city-2641673-hold-session-session-669150ea5b3ca:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
6	http://leucois9ux-mobile-country-GB-state-6269131-city-2643123-hold-session-session-6691514c10fbc:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
7	http://leucois9ux-mobile-country-GB-state-6269131-city-2654993-hold-session-session-669152a4a998a:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
8	http://leucois9ux-mobile-country-GB-state-6269131-city-6545250-hold-session-session-669152b3be731:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
9	http://leucois9ux-mobile-country-GB-state-6269131-city-3333200-hold-session-session-669152c227078:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
10	http://leucois9ux-mobile-country-GB-state-6269131-city-2634812-hold-session-session-669152d1ae60b:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
11	http://leucois9ux-mobile-country-GB-state-6269131-city-2643743-hold-session-session-669153104265b:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
12	http://leucois9ux-mobile-country-GB-state-6269131-city-2644688-hold-session-session-6691531b21756:eThapYQvdMX5Tttn@93.190.138.107:9999\r\n	f
\.


--
-- TOC entry 4944 (class 0 OID 16634)
-- Dependencies: 229
-- Data for Name: text; Type: TABLE DATA; Schema: config; Owner: -
--

COPY config.text (key, value) FROM stdin;
debug_key	C0D3-TH1S-1S-JU5T-T35T
debug_game	C0D3
api_token	6567944149:AAE8bPXXugVGg67sqm5XNi4vcH2dSDLqoo4
\.


--
-- TOC entry 4938 (class 0 OID 16478)
-- Dependencies: 223
-- Data for Name: cache; Type: TABLE DATA; Schema: hamster-kombat-keys; Owner: -
--

COPY "hamster-kombat-keys".cache (id, user_id, welcome, loading, report, process, error, tasks, addtask, deletetask) FROM stdin;
403	454	3708	3693	\N	t	\N	0	\N	\N
470	521	4647	4646	\N	t	\N	0	\N	\N
444	495	4206	4204	\N	t	\N	1	\N	\N
486	537	4855	\N	\N	t	\N	0	\N	\N
456	507	4514	4513	\N	t	\N	0	\N	\N
419	470	5724	5723	\N	t	\N	0	\N	\N
473	524	4711	4710	\N	t	\N	0	\N	\N
466	517	4605	4604	\N	t	\N	0	\N	\N
379	430	3494	3493	\N	t	\N	0	\N	\N
528	579	5780	5779	\N	t	\N	0	\N	\N
501	552	5060	\N	\N	t	\N	0	\N	\N
467	518	4607	4601	\N	t	\N	0	\N	\N
448	499	4498	\N	\N	t	\N	0	\N	\N
357	408	1931	1928	\N	t	\N	0	\N	\N
385	436	3663	3660	\N	t	\N	0	\N	\N
347	398	1871	1870	\N	t	\N	0	\N	\N
516	567	5419	5418	\N	t	\N	0	\N	\N
530	581	5782	\N	\N	t	\N	0	\N	\N
423	474	3995	3994	\N	t	\N	0	\N	\N
446	497	4463	4462	\N	t	\N	0	\N	\N
517	568	5439	\N	\N	t	\N	0	\N	\N
384	435	\N	\N	\N	t	\N	0	\N	\N
383	434	3496	\N	\N	t	\N	0	\N	\N
479	530	4784	\N	\N	t	\N	0	\N	\N
555	606	6161	6165	\N	t	\N	1	\N	\N
452	502	4523	4521	\N	t	\N	0	\N	\N
462	513	\N	\N	\N	t	\N	0	\N	\N
394	445	3702	3698	\N	t	\N	0	\N	\N
346	397	5057	5056	\N	t	\N	0	\N	\N
377	428	3475	\N	\N	t	\N	0	\N	\N
563	614	6361	6360	\N	t	\N	0	\N	\N
566	617	6356	6355	\N	t	\N	0	\N	\N
535	586	5911	5910	\N	t	\N	0	\N	\N
461	512	\N	\N	\N	t	\N	0	\N	\N
472	523	4662	\N	\N	t	\N	0	\N	\N
531	582	5791	5790	\N	t	\N	0	\N	\N
370	421	5030	5033	\N	t	\N	0	\N	\N
463	514	\N	\N	\N	t	\N	0	\N	\N
436	487	4131	4130	\N	t	\N	0	\N	\N
372	423	3454	\N	\N	t	\N	0	\N	\N
373	424	3457	\N	\N	t	\N	0	\N	\N
366	417	\N	\N	\N	t	\N	0	\N	\N
484	535	5376	5363	\N	t	\N	0	\N	\N
571	622	6426	\N	\N	t	\N	0	\N	\N
541	592	5881	\N	\N	t	\N	0	\N	\N
407	458	5935	5926	\N	t	\N	0	\N	\N
551	602	6211	6204	\N	t	\N	1	\N	\N
421	472	3920	\N	\N	t	\N	0	\N	\N
590	641	8659	8661	\N	t	\N	0	\N	\N
524	575	5705	5704	\N	t	\N	0	\N	\N
561	612	6333	6332	\N	t	6300	0	\N	\N
398	449	3905	3904	\N	t	\N	0	\N	\N
549	600	\N	\N	\N	t	\N	0	\N	\N
387	438	\N	\N	\N	t	\N	0	\N	\N
428	479	4121	4120	\N	t	\N	0	\N	\N
548	599	5937	\N	\N	t	\N	0	\N	\N
522	573	5627	\N	\N	t	\N	0	\N	\N
338	389	8674	8546	8663	t	\N	0	\N	\N
568	619	7834	7904	\N	t	\N	0	\N	\N
487	538	4896	4895	\N	t	\N	0	\N	\N
353	404	1913	1912	\N	t	\N	0	\N	\N
523	574	5692	\N	\N	t	\N	0	\N	\N
431	482	4095	4094	\N	t	\N	0	\N	\N
445	496	4197	4191	\N	t	\N	1	\N	\N
459	510	4550	4548	\N	t	\N	0	\N	\N
588	639	8478	8475	\N	t	8481	0	\N	\N
503	554	\N	\N	\N	t	\N	0	\N	\N
409	460	3882	3877	\N	t	\N	0	\N	\N
429	480	4160	4159	\N	t	\N	0	\N	\N
485	536	4852	4851	\N	t	\N	0	\N	\N
340	391	1776	1775	\N	t	\N	0	\N	\N
410	461	3832	3830	\N	t	\N	0	\N	\N
439	490	4151	4150	\N	t	\N	0	\N	\N
460	511	\N	\N	\N	t	\N	0	\N	\N
465	516	4582	\N	\N	t	\N	0	\N	\N
364	415	\N	\N	\N	t	\N	0	\N	\N
442	493	4153	\N	\N	t	\N	0	\N	\N
344	395	8703	8698	\N	t	\N	3	\N	\N
481	532	4892	4826	\N	t	\N	0	\N	\N
341	392	8707	\N	\N	t	\N	0	\N	\N
354	405	1889	1888	\N	t	\N	0	\N	\N
521	572	5617	\N	\N	t	\N	0	\N	\N
361	412	1933	\N	\N	t	\N	0	\N	\N
424	475	3979	3978	\N	t	\N	0	\N	\N
363	414	2433	2431	\N	t	\N	0	\N	\N
\.


--
-- TOC entry 4936 (class 0 OID 16451)
-- Dependencies: 221
-- Data for Name: keys; Type: TABLE DATA; Schema: hamster-kombat-keys; Owner: -
--

COPY "hamster-kombat-keys".keys (id, user_id, key, type, "time", used, game_id) FROM stdin;
970	389	CUBE-Y59-XGRL-YGHS-FPP	CUBE	1723886648	t	1
971	389	CUBE-X51-PPDW-Y6JY-RWL	CUBE	1723886648	t	1
972	389	CUBE-X6H-13RG-YLJA-PRW	CUBE	1723886648	t	1
973	389	CUBE-W61-1N15-YWF4-HYF	CUBE	1723886648	t	1
978	641	C0D3-TH1S-1S-JU5T-T35T-428137C41585D566	BIKE	1724084729	t	1
979	641	C0D3-TH1S-1S-JU5T-T35T-09D9944A8A932A54	BIKE	1724084730	t	1
780	460	CODE-TH1S-1S-JU5T-T35T-68EC452DE931DA49	CLONE	1723476977	t	1
781	460	CODE-TH1S-1S-JU5T-T35T-7ACC07158647EAB4	CUBE	1723476978	t	1
782	461	CODE-TH1S-1S-JU5T-T35T-8A3D5BE0C8B12500	CLONE	1723477254	t	1
783	461	CODE-TH1S-1S-JU5T-T35T-715952BAE1C53712	CLONE	1723477530	t	1
784	461	CODE-TH1S-1S-JU5T-T35T-8D2E7AB754EC874A	TRAIN	1723477757	t	1
785	449	CODE-TH1S-1S-JU5T-T35T-96657E361076132C	BIKE	1723478424	t	1
786	460	CODE-TH1S-1S-JU5T-T35T-2C292887EE8D9C29	TRAIN	1723478443	t	1
787	460	CODE-TH1S-1S-JU5T-T35T-29B46B815BACB54B	BIKE	1723478445	t	1
788	460	CODE-TH1S-1S-JU5T-T35T-26990558C244A86D	BIKE	1723478452	t	1
789	449	CODE-TH1S-1S-JU5T-T35T-EB6267CE3A50A78C	BIKE	1723478553	t	1
790	460	CODE-TH1S-1S-JU5T-T35T-56393C087D30D572	CLONE	1723478560	t	1
791	460	CODE-TH1S-1S-JU5T-T35T-0D45B078BE204329	TRAIN	1723478566	t	1
792	460	CODE-TH1S-1S-JU5T-T35T-BAB7D85334507233	TRAIN	1723478568	t	1
793	460	CODE-TH1S-1S-JU5T-T35T-3DE5BA203B5EAA0E	TRAIN	1723478569	t	1
794	460	CODE-TH1S-1S-JU5T-T35T-08B62624B9343D61	CUBE	1723478573	t	1
795	449	CODE-TH1S-1S-JU5T-T35T-ED0EDE42C25C3566	CLONE	1723478717	t	1
796	449	CODE-TH1S-1S-JU5T-T35T-134D66B6726D4DB7	TRAIN	1723478840	t	1
797	449	CODE-TH1S-1S-JU5T-T35T-9284C1DB94211A30	CUBE	1723478981	t	1
798	395	CODE-TH1S-1S-JU5T-T35T-1D7E90D13477D6B3	CLONE	1723479488	t	1
799	395	CODE-TH1S-1S-JU5T-T35T-6786D140AC966BE5	CUBE	1723479510	t	1
800	395	CODE-TH1S-1S-JU5T-T35T-4CC2E16853E8CC5A	TRAIN	1723479531	t	1
801	395	CODE-TH1S-1S-JU5T-T35T-562D45127B0BA3E7	BIKE	1723479551	t	1
802	474	CODE-TH1S-1S-JU5T-T35T-225562AC041E8028	TRAIN	1723480029	t	1
803	474	CODE-TH1S-1S-JU5T-T35T-5254D542711CB370	TRAIN	1723480124	t	1
804	474	CODE-TH1S-1S-JU5T-T35T-59D004A3AD8A14AC	TRAIN	1723480358	t	1
727	602	CODE-TH1S-1S-JU5T-T35T-93ECA6A368520466	TRAIN	1723815062	t	1
728	612	CODE-TH1S-1S-JU5T-T35T-3156AEC495E249D1	TRAIN	1723817124	t	1
731	612	CODE-TH1S-1S-JU5T-T35T-B835882AC3C5B1A1	TRAIN	1723817166	t	1
729	395	CODE-TH1S-1S-JU5T-T35T-5283D5CB692AD64E	BIKE	1723277684	f	1
730	397	CODE-TH1S-1S-JU5T-T35T-5C1AB66C5E73328D	CUBE	1723277955	f	1
742	612	CODE-TH1S-1S-JU5T-T35T-9933AB23D1E6C1E7	TRAIN	1723817697	t	1
732	398	CODE-TH1S-1S-JU5T-T35T-3AD0D55283D48C5A	BIKE	1723278088	f	1
734	398	CODE-TH1S-1S-JU5T-T35T-D1D941C7945D251E	BIKE	1723278139	f	1
735	395	CODE-TH1S-1S-JU5T-T35T-37142DD2BE5D0E0D	CUBE	1723278191	f	1
736	398	CODE-TH1S-1S-JU5T-T35T-DDCAA208B10A4D47	BIKE	1723278402	f	1
737	398	CODE-TH1S-1S-JU5T-T35T-2E91A51E9AD23410	CLONE	1723278410	f	1
738	398	CODE-TH1S-1S-JU5T-T35T-E1638067CA12A316	CUBE	1723278442	f	1
739	395	CODE-TH1S-1S-JU5T-T35T-6D728A7450ED4888	CLONE	1723278471	f	1
740	395	CODE-TH1S-1S-JU5T-T35T-71AB55E5468C591A	CUBE	1723278486	f	1
743	395	CODE-TH1S-1S-JU5T-T35T-3B451CDD89A8EBA7	BIKE	1723278619	f	1
744	395	CODE-TH1S-1S-JU5T-T35T-CD41A04AEB5D85A4	CLONE	1723278638	f	1
726	602	CODE-TH1S-1S-JU5T-T35T-05555A460010B594	CLONE	1723815062	t	1
805	475	CODE-TH1S-1S-JU5T-T35T-BD20297C19AA0929	BIKE	1723480550	t	1
806	474	CODE-TH1S-1S-JU5T-T35T-57ACA0A0AC35B8E6	CLONE	1723481029	t	1
807	474	CODE-TH1S-1S-JU5T-T35T-76018A7B0A71873C	TRAIN	1723481063	t	1
808	479	CODE-TH1S-1S-JU5T-T35T-0BA5041B017E4C56	BIKE	1723484331	t	1
809	479	CODE-TH1S-1S-JU5T-T35T-EBAB6ED9E89E5EB6	BIKE	1723484563	t	1
810	480	CODE-TH1S-1S-JU5T-T35T-A0477E8582A6EAEB	BIKE	1723484719	t	1
811	479	CODE-TH1S-1S-JU5T-T35T-02440C11BBB8142B	BIKE	1723484724	t	1
812	482	CODE-TH1S-1S-JU5T-T35T-C6562A924335AEB5	BIKE	1723484799	t	1
813	480	CODE-TH1S-1S-JU5T-T35T-558AC0B2381A549B	BIKE	1723484873	t	1
814	487	CODE-TH1S-1S-JU5T-T35T-6C8EA63A6A4D7344	TRAIN	1723485067	t	1
815	479	CODE-TH1S-1S-JU5T-T35T-B23999E7AD022A83	CLONE	1723485078	t	1
816	487	CODE-TH1S-1S-JU5T-T35T-5D9BEE5B8D9C7321	CUBE	1723485113	t	1
817	487	CODE-TH1S-1S-JU5T-T35T-B36B9718B143E3E4	TRAIN	1723485245	t	1
818	490	CODE-TH1S-1S-JU5T-T35T-A08E3E9EBEDB3DEE	BIKE	1723485828	t	1
819	480	CODE-TH1S-1S-JU5T-T35T-1683BD67AC439E27	BIKE	1723486947	t	1
820	389	CODE-TH1S-1S-JU5T-T35T-857D21A0AC177244	TRAIN	1723487436	t	1
821	389	CODE-TH1S-1S-JU5T-T35T-9014B088EA4D7873	CLONE	1723487454	t	1
822	495	CODE-TH1S-1S-JU5T-T35T-1E15DB1134C1E3EB	CLONE	1723487493	t	1
823	496	CODE-TH1S-1S-JU5T-T35T-70DA517378908484	BIKE	1723487494	t	1
824	496	CODE-TH1S-1S-JU5T-T35T-A78202ED4831833A	CUBE	1723487495	t	1
825	496	CODE-TH1S-1S-JU5T-T35T-58B5D7546B331B6A	TRAIN	1723487497	t	1
826	496	CODE-TH1S-1S-JU5T-T35T-0CA110302BA2186D	CLONE	1723487500	t	1
827	495	CODE-TH1S-1S-JU5T-T35T-C6B982EECEE9414A	CLONE	1723487664	t	1
828	495	CODE-TH1S-1S-JU5T-T35T-A7A39B3417E2B2E0	CLONE	1723487666	t	1
829	497	CODE-TH1S-1S-JU5T-T35T-8A26D115C5D2A33E	BIKE	1723547021	t	1
830	502	CODE-TH1S-1S-JU5T-T35T-4B1D43CD259E4B73	BIKE	1723548935	t	1
831	502	CODE-TH1S-1S-JU5T-T35T-2907800027684368	BIKE	1723549134	t	1
832	507	CODE-TH1S-1S-JU5T-T35T-D5C452853B51A8AD	BIKE	1723550163	t	1
833	502	CODE-TH1S-1S-JU5T-T35T-B17445BD8935ADC6	BIKE	1723550869	t	1
834	502	CODE-TH1S-1S-JU5T-T35T-B4B82A438319A42D	CUBE	1723550870	t	1
835	510	CODE-TH1S-1S-JU5T-T35T-3CA28BB811C962EE	BIKE	1723552147	t	1
836	510	CODE-TH1S-1S-JU5T-T35T-B57A5CD3A2A24795	BIKE	1723552318	t	1
837	517	C0D3-TH1S-1S-JU5T-T35T-DD81D58E85A2B3D8	BIKE	1723559705	t	1
838	518	C0D3-TH1S-1S-JU5T-T35T-62EBD9189943BE42	BIKE	1723559751	t	1
839	517	C0D3-TH1S-1S-JU5T-T35T-E2B5E1873A0DD6D5	BIKE	1723559762	t	1
840	458	C0D3-TH1S-1S-JU5T-T35T-9310C663D0656E43	BIKE	1723562310	t	1
841	521	C0D3-TH1S-1S-JU5T-T35T-1678BA79A3D57646	BIKE	1723563110	t	1
842	521	C0D3-TH1S-1S-JU5T-T35T-627B1B470160090D	BIKE	1723563186	t	1
843	521	C0D3-TH1S-1S-JU5T-T35T-36D2386A6373ED56	BIKE	1723563264	t	1
844	521	C0D3-TH1S-1S-JU5T-T35T-A671E80A5D743A57	BIKE	1723563297	t	1
845	421	C0D3-TH1S-1S-JU5T-T35T-3AB9E62421BD7379	BIKE	1723563514	t	1
846	524	C0D3-TH1S-1S-JU5T-T35T-214BE365C754905B	BIKE	1723566862	t	1
847	524	C0D3-TH1S-1S-JU5T-T35T-B8578BC7633CEDD9	BIKE	1723567086	t	1
848	395	C0D3-TH1S-1S-JU5T-T35T-96A165B4399B3E74	CLONE	1723569811	t	1
849	395	C0D3-TH1S-1S-JU5T-T35T-CE9D4C618DAB285A	CLONE	1723570451	t	1
850	532	C0D3-TH1S-1S-JU5T-T35T-71300A45434781BB	CLONE	1723570455	t	1
851	395	C0D3-TH1S-1S-JU5T-T35T-DAA3B938DC9EDED8	TRAIN	1723570462	t	1
852	395	C0D3-TH1S-1S-JU5T-T35T-E8E5067254AA1855	TRAIN	1723570472	t	1
853	532	C0D3-TH1S-1S-JU5T-T35T-87C3D59DC7C1DAD5	CLONE	1723570666	t	1
854	535	C0D3-TH1S-1S-JU5T-T35T-9655665A67C5A0DA	CLONE	1723570754	t	1
855	535	C0D3-TH1S-1S-JU5T-T35T-2481B3DB5A705830	TRAIN	1723570869	t	1
856	532	C0D3-TH1S-1S-JU5T-T35T-B2B605CC34B5DACD	BIKE	1723571007	t	1
857	536	C0D3-TH1S-1S-JU5T-T35T-17750C9AC5E4A3B9	BIKE	1723571260	t	1
858	536	C0D3-TH1S-1S-JU5T-T35T-0BC436AC5EEC285E	CUBE	1723571409	t	1
859	538	C0D3-TH1S-1S-JU5T-T35T-A02EEB538A53291B	BIKE	1723571680	t	1
860	538	C0D3-TH1S-1S-JU5T-T35T-930B7BC91A1BED80	BIKE	1723572289	t	1
861	538	C0D3-TH1S-1S-JU5T-T35T-4DEB186B835398A3	CUBE	1723572323	t	1
862	458	C0D3-TH1S-1S-JU5T-T35T-A45888604C4EAAEB	BIKE	1723572388	t	1
863	538	C0D3-TH1S-1S-JU5T-T35T-495A7A54C60D7CCE	CLONE	1723572839	t	1
864	421	C0D3-TH1S-1S-JU5T-T35T-82D0753548841DC4	BIKE	1723581217	t	1
865	421	C0D3-TH1S-1S-JU5T-T35T-E7D1395C3C446BA3	CLONE	1723581370	t	1
866	397	C0D3-TH1S-1S-JU5T-T35T-D714E0A63A237D93	BIKE	1723581650	t	1
867	554	C0D3-TH1S-1S-JU5T-T35T-572A035A35AA9910	CUBE	1723612403	f	1
868	554	C0D3-TH1S-1S-JU5T-T35T-A621E1B1519B5624	CUBE	1723612403	f	1
869	554	C0D3-TH1S-1S-JU5T-T35T-89B489C574311DDA	CUBE	1723612403	f	1
870	554	C0D3-TH1S-1S-JU5T-T35T-751264BC9485B8B6	BIKE	1723612404	f	1
871	554	C0D3-TH1S-1S-JU5T-T35T-BCC4E3A706B35D63	BIKE	1723612406	f	1
872	554	C0D3-TH1S-1S-JU5T-T35T-8573BD5EE8D2A032	CLONE	1723612406	f	1
974	389	C0D3-TH1S-1S-JU5T-T35T-20665C52543D27BD	CUBE	1724010763	t	1
874	554	C0D3-TH1S-1S-JU5T-T35T-4A0EB9474CC1B86E	CLONE	1723612408	f	1
876	554	C0D3-TH1S-1S-JU5T-T35T-7CC6669AA1714696	BIKE	1723612409	f	1
877	554	C0D3-TH1S-1S-JU5T-T35T-8546ECA5C60E3086	CLONE	1723612411	f	1
878	554	C0D3-TH1S-1S-JU5T-T35T-7B404A9DB1185EA7	TRAIN	1723612412	f	1
879	554	CUBE-ZSP-W83M-YCDZ-3HS	CUBE	1723612518	f	1
875	612	C0D3-TH1S-1S-JU5T-T35T-AC413269B3B7CC04	TRAIN	1723817781	t	1
880	554	CUBE-ZR8-TS7L-YGBF-V56	CUBE	1723612522	f	1
881	554	CUBE-YRC-WXKJ-Y4DZ-GSN	CUBE	1723612534	f	1
882	395	TRAIN-XPZ-EH8E-YQYY-BVM	TRAIN	1723624635	t	1
883	395	TRAIN-XQB-LNYM-Y7YQ-VTJ	TRAIN	1723624852	t	1
884	395	CLONE-XPP-2Q5J-YSZY-X88	CLONE	1723625402	t	1
885	395	CUBE-WQ8-MKEA-YMZ7-2E3	CUBE	1723625898	t	1
886	535	CLONE-ZPM-6ESB-YFWH-6PL	CLONE	1723626482	t	1
887	535	CUBE-XPS-5J29-YKZR-55E	CUBE	1723626651	t	1
888	535	TRAIN-YQD-75MK-YSWT-FEM	TRAIN	1723626866	t	1
889	535	CLONE-YP1-KW1F-YBWK-2CB	CLONE	1723627068	t	1
890	567	C0D3-TH1S-1S-JU5T-T35T-A44B93619AB13B8A	BIKE	1723643809	t	1
891	567	C0D3-TH1S-1S-JU5T-T35T-2ADEA63D2DC60BEC	BIKE	1723643859	t	1
892	395	C0D3-TH1S-1S-JU5T-T35T-C3BE8619A692D099	CLONE	1723708134	t	1
893	575	C0D3-TH1S-1S-JU5T-T35T-D6D407EE9BC94EB4	MERGE	1723725572	t	1
894	575	C0D3-TH1S-1S-JU5T-T35T-6558E9A9C829400B	CUBE	1723725725	t	1
895	470	C0D3-TH1S-1S-JU5T-T35T-ECA114B27CA86AD3	MERGE	1723726360	t	1
896	470	C0D3-TH1S-1S-JU5T-T35T-C0C101C7A3911459	CUBE	1723726420	t	1
897	395	C0D3-TH1S-1S-JU5T-T35T-51108B6E25C6A433	MERGE	1723727585	t	1
898	389	C0D3-TH1S-1S-JU5T-T35T-7CC92C020D88931E	MERGE	1723727789	t	1
899	579	C0D3-TH1S-1S-JU5T-T35T-449BA75CA3D6D6CD	BIKE	1723728405	t	1
910	458	C0D3-TH1S-1S-JU5T-T35T-E6A33334005BBA69	CUBE	1723735318	t	1
911	389	C0D3-TH1S-1S-JU5T-T35T-D4961B686A9DCB31	MERGE	1723741560	t	1
913	395	C0D3-TH1S-1S-JU5T-T35T-E8698EA3075CA710	CLONE	1723742298	t	1
914	395	C0D3-TH1S-1S-JU5T-T35T-EB2EE0E690A73AD6	BIKE	1723742316	t	1
733	398	CODE-TH1S-1S-JU5T-T35T-DAA9B4C3D8C12377	CUBE	1723278117	f	1
975	389	C0D3-TH1S-1S-JU5T-T35T-1EC78D8512237193	CUBE	1724010763	t	1
976	389	C0D3-TH1S-1S-JU5T-T35T-9B287833B73A6E7E	CUBE	1724010763	t	1
977	389	C0D3-TH1S-1S-JU5T-T35T-BE346C28538B61B4	CUBE	1724010763	t	1
980	395	C0D3-TH1S-1S-JU5T-T35T-4008E9106EE79CD7	BIKE	1724087380	t	1
981	395	C0D3-TH1S-1S-JU5T-T35T-64EA98E80E318065	BIKE	1724087380	t	1
982	395	C0D3-TH1S-1S-JU5T-T35T-287C0D177539C5B9	BIKE	1724087380	t	1
983	395	C0D3-TH1S-1S-JU5T-T35T-541495D95D9C9228	BIKE	1724087380	t	1
907	586	C0D3-TH1S-1S-JU5T-T35T-83543B773A55EA73	MERGE	1723733599	f	1
908	395	C0D3-TH1S-1S-JU5T-T35T-0740CBC0645BE1D8	MERGE	1723734334	f	1
909	458	C0D3-TH1S-1S-JU5T-T35T-5EB36E119EB5EE9E	BIKE	1723735280	f	1
912	395	C0D3-TH1S-1S-JU5T-T35T-A51225E5D909A1B7	MERGE	1723742283	f	1
900	389	MERGE-W2N-DJ48-YJT6-6NT	MERGE	1723776956	t	1
916	389	TWERK-W43-RYD8-YLBE-KTZ	TWERK	1723813037	t	1
725	606	CODE-TH1S-1S-JU5T-T35T-27DCE25210BAA4D4	BIKE	1723813316	t	1
918	602	C0D3-TH1S-1S-JU5T-T35T-2E6777BECD591A92	TWERK	1723814925	t	1
901	602	MERGE-W2J-A1KK-YGV6-JHB	MERGE	1723815062	t	1
902	602	MERGE-W1J-MAL5-YWRC-CGL	MERGE	1723815064	t	1
903	612	MERGE-X16-J3D1-YLRE-DQ1	MERGE	1723817211	t	1
904	612	C0D3-TH1S-1S-JU5T-T35T-6CA2705442906D18	MERGE	1723817273	t	1
927	612	TWERK-W37-AX4N-YGH1-YCT	TWERK	1723817577	t	1
873	612	C0D3-TH1S-1S-JU5T-T35T-B18CD7D79885B4E9	TRAIN	1723817747	t	1
905	612	C0D3-TH1S-1S-JU5T-T35T-3C5D51729C4849C3	MERGE	1723817834	t	1
906	612	C0D3-TH1S-1S-JU5T-T35T-3B496E436A3BA8A9	MERGE	1723817900	t	1
933	614	TWERK-X3X-APKC-YYFM-T1Z	TWERK	1723819812	t	1
934	617	TWERK-Z4H-M8NH-YAGJ-VLK	TWERK	1723819968	t	1
935	614	TWERK-Z3J-SSWJ-Y8JQ-JHZ	TWERK	1723820153	t	1
936	619	TWERK-Y3W-4VEF-YGJQ-W6L	TWERK	1723820397	t	1
937	619	TWERK-W4R-8YZ8-YPGF-BM6	TWERK	1723820673	t	1
938	619	TWERK-W32-HCJZ-YTF9-MAE	TWERK	1723821005	t	1
984	395	C0D3-TH1S-1S-JU5T-T35T-DB8E2CC6B819DB09	MERGE	1724087431	t	1
985	395	C0D3-TH1S-1S-JU5T-T35T-10B1E6497946ADE9	MERGE	1724087431	t	1
986	395	C0D3-TH1S-1S-JU5T-T35T-4D26AAB9D852A1C0	MERGE	1724087431	t	1
987	395	C0D3-TH1S-1S-JU5T-T35T-B6A5C135465511BE	MERGE	1724087431	t	1
988	395	C0D3-TH1S-1S-JU5T-T35T-9C2894191CDADCE1	MERGE	1724087540	t	1
989	395	C0D3-TH1S-1S-JU5T-T35T-DAA1A8D318B69562	MERGE	1724087540	t	1
990	395	C0D3-TH1S-1S-JU5T-T35T-EB1D659D09C4DD0C	MERGE	1724087540	t	1
991	395	C0D3-TH1S-1S-JU5T-T35T-5573DA1D3706B7E6	MERGE	1724087540	t	1
\.


--
-- TOC entry 4934 (class 0 OID 16400)
-- Dependencies: 219
-- Data for Name: users; Type: TABLE DATA; Schema: hamster-kombat-keys; Owner: -
--

COPY "hamster-kombat-keys".users (id, tg_username, tg_id, ref_id, "right", lang) FROM stdin;
622	Danielps9	597076613	0	0	en
474	SergOnTelegram	760561852	0	0	en
391	ZeroDevops	960878279	0	0	ru
574	Ajaykumar9129	1393714383	0	0	en
398	Hichamazz	6693448035	0	0	en
532	hteatsix69nine	1946069754	0	0	en
475	mahdi909713	307285677	0	0	en
479	AmirDaghighi	80006598	0	0	en
405	Ulama200	5979336415	0	0	en
404	Omidi_86	1061979368	0	0	en
619	Johandrysitumorang	6931892858	0	0	en
408	syv00100	5896536528	364576722	0	en
412	Muhammadmusabello	6583108879	0	0	en
414	shadiphilosophia	85940872	0	0	en
415	BellesHub	5186720131	1265045387	0	en
575	Ahmet4891	6393961420	6601480817	0	en
417	DawudAbdullahi	6638020224	0	0	en
482	Saudat80	6226639924	0	0	en
480	abcdefu50	5000879526	0	0	en
423	ajstylesxx	1236263452	0	0	en
487	Ar_mgorji	864199250	0	0	en
424	Chronologi7	540998698	0	0	en
428	sd_musclefreak	1092506917	0	0	en
470	Ahmet19841007	6601480817	0	0	ru
490	alireza_sufi	601359697	0	0	en
430	karenminer	2031984540	0	0	en
434	Hassanmadugu	6719646513	0	0	en
435	mahnaz1365kord	1794472322	0	0	en
493	CharlseySimon	6511594443	0	0	en
438	Aqeel4445	5570923647	0	0	en
579	daniel4uall	6887133910	0	0	en
495	Gh_mehrad	90726090	0	0	en
496	az09alli	5402473765	0	0	en
421	Aishooshoo	2079938582	2031984540	0	en
497	Iniisofitness247	6230844641	0	0	en
436	napepe00	1495300389	0	0	en
449	amit8764133613	6944422827	0	0	en
581	OTYUKO	877111950	0	0	en
606	barcel10a	580353006	0	0	en
445	Ebbiereyjnr	6916237971	0	0	en
454	Osaja11	6589736545	0	0	en
461	mohsenshoko	57779290	0	0	en
552	Ali_manavi00	6478479893	7401023720	0	en
499	amirr_r18	1342816032	103817927	0	en
507	Sammygraphix	1260250889	1265045387	0	en
502	reza65450	7028835712	0	0	en
460	ARBakhshali	155999254	0	0	en
510	yasin9388	6612439147	0	0	en
554	tonfastbot	6567944149	0	0	en
582	loganmhm47	5075397775	6139984178	0	en
472	Shadow0001000	7051705882	0	0	ru
511	Yas9388	922785553	0	0	ru
512	Gabbarsingh32	5233332414	6230935201	0	en
513	Benhuh	625214033	1265045387	0	en
514	Tagwaijr	5545507250	0	0	en
516	HunterX444hunt	6857033955	0	0	en
517	wallydigs	7094584378	0	0	en
518	lambojam	6717808884	7094584378	0	en
521	Rahulkasari	1260167783	0	0	en
389	smilegreenlight	5043492422	0	9	ru
524	hhihggfgh	5376687918	0	0	en
639	M1821jshtapim	139509395	0	0	en
586	cykablyat999	7218645943	0	0	en
530	aysgks	7494087683	0	0	ru
602	Ismailwolf	7483250317	0	0	en
536	AdityaA_lone	5193637901	6150967068	0	en
537	Nuratuge1	7048398965	0	0	en
538	Whillerg	5009017192	0	0	ru
612	hs_rood	6053355731	0	0	en
592	zekridd	757569040	0	0	en
535	mhmtatg	1854655750	0	0	en
567	Milobaonk	261267616	1023403979	0	en
568	Anosh3660	290440560	6765249188	0	en
397	salihbalc61	970903621	0	0	en
523	Gebre217	7211785491	0	0	en
572	rafieiali	67869839	0	0	en
573	Xoshym	929042322	0	0	en
614	wzpower	1050021044	6706619251	0	en
458	nicomeza	736247017	0	0	en
599	sultan9598	857845445	0	0	en
600	martinsivanovs963	7132214230	7218645943	0	en
617	Beysef	5349024164	6706619251	0	en
641	Salman7736Ansari	6939977871	0	0	en
395	Cryptovampix	5004043949	0	0	ru
392	CryptoT_cat	1654020905	0	0	ru
\.


--
-- TOC entry 4941 (class 0 OID 16577)
-- Dependencies: 226
-- Data for Name: checker; Type: TABLE DATA; Schema: promotion; Owner: -
--

COPY promotion.checker (id, promo_id, user_id) FROM stdin;
7	6	395
14	8	470
15	8	395
17	8	458
18	8	389
20	8	395
21	15	389
22	15	389
23	15	389
24	15	619
25	15	619
26	15	619
27	15	619
\.


--
-- TOC entry 4940 (class 0 OID 16572)
-- Dependencies: 225
-- Data for Name: games; Type: TABLE DATA; Schema: promotion; Owner: -
--

COPY promotion.games (id, name, "desc", link) FROM stdin;
1	Hamster Kombat	Ключи от игр Hamster Kombat	https://t.me/hamster_kombat_bot
\.


--
-- TOC entry 4939 (class 0 OID 16567)
-- Dependencies: 224
-- Data for Name: promo; Type: TABLE DATA; Schema: promotion; Owner: -
--

COPY promotion.promo (name, "desc", link, check_id, control, type, id) FROM stdin;
Канал обновлений	Подпишитесь на канал, чтобы узнавать о последних обновлениях в боте и следить за будущими событиями	https://t.me/+KXHlwsa-j5c3MGU6	-1002215114043	1	task	5
Name of task 1	Description of task 1	https://t.me/+qXTEFTc3AsgwMWZi	-1002167390063	1	task	8
Имя of task 2	Описание of task 2	https://t.me/+dnhjQX_na000NWUy	-1002217574534	1	task	15
\.


--
-- TOC entry 4949 (class 0 OID 16660)
-- Dependencies: 234
-- Data for Name: promo_prizes; Type: TABLE DATA; Schema: promotion; Owner: -
--

COPY promotion.promo_prizes (id, promo_id, name, winner_id, owner_id) FROM stdin;
\.


--
-- TOC entry 4943 (class 0 OID 16582)
-- Dependencies: 228
-- Data for Name: promo_translate; Type: TABLE DATA; Schema: promotion; Owner: -
--

COPY promotion.promo_translate (id, lang, type, value, promo_id) FROM stdin;
10	ru	name	Канал обновлений	5
11	ru	desc	Подпишитесь на канал, чтобы узнавать о последних обновлениях в боте и следить за будущими событиями	5
12	ru	link	https://t.me/+KXHlwsa-j5c3MGU6	5
13	en	name	Update channel	5
14	en	desc	Subscribe to channel to know about updates	5
15	en	link	https://t.me/+KXHlwsa-j5c3MGU6	5
16	ru	name	Name of task 1	8
17	ru	desc	Description of task 1	8
18	ru	link	https://t.me/+qXTEFTc3AsgwMWZi	8
19	en	name	Имя of task 1	8
20	en	desc	Описание of task 1	8
21	en	link	https://t.me/+qXTEFTc3AsgwMWZi	8
41	ru	name	Имя of task 2	15
42	ru	desc	Описание of task 2	15
43	ru	id	-1002217574534	15
44	ru	check_id	-1002217574534	15
45	ru	link	https://t.me/+dnhjQX_na000NWUy	15
46	en	name	of task 2	15
47	en	desc	Description of task 2	15
48	en	id	-1002217574534	15
49	en	check_id	-1002217574534	15
50	en	link	https://t.me/+dnhjQX_na000NWUy	15
\.


--
-- TOC entry 4957 (class 0 OID 0)
-- Dependencies: 231
-- Name: proxy_id_seq; Type: SEQUENCE SET; Schema: config; Owner: -
--

SELECT pg_catalog.setval('config.proxy_id_seq', 12, true);


--
-- TOC entry 4958 (class 0 OID 0)
-- Dependencies: 222
-- Name: cashe_id_seq; Type: SEQUENCE SET; Schema: hamster-kombat-keys; Owner: -
--

SELECT pg_catalog.setval('"hamster-kombat-keys".cashe_id_seq', 593, true);


--
-- TOC entry 4959 (class 0 OID 0)
-- Dependencies: 220
-- Name: keys_id_seq; Type: SEQUENCE SET; Schema: hamster-kombat-keys; Owner: -
--

SELECT pg_catalog.setval('"hamster-kombat-keys".keys_id_seq', 991, true);


--
-- TOC entry 4960 (class 0 OID 0)
-- Dependencies: 218
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: hamster-kombat-keys; Owner: -
--

SELECT pg_catalog.setval('"hamster-kombat-keys".users_id_seq', 644, true);


--
-- TOC entry 4961 (class 0 OID 0)
-- Dependencies: 227
-- Name: newtable_id_seq; Type: SEQUENCE SET; Schema: promotion; Owner: -
--

SELECT pg_catalog.setval('promotion.newtable_id_seq', 50, true);


--
-- TOC entry 4962 (class 0 OID 0)
-- Dependencies: 235
-- Name: promo_id_seq; Type: SEQUENCE SET; Schema: promotion; Owner: -
--

SELECT pg_catalog.setval('promotion.promo_id_seq', 15, true);


--
-- TOC entry 4963 (class 0 OID 0)
-- Dependencies: 233
-- Name: promo_prizes_id_seq; Type: SEQUENCE SET; Schema: promotion; Owner: -
--

SELECT pg_catalog.setval('promotion.promo_prizes_id_seq', 1, false);


--
-- TOC entry 4774 (class 2606 OID 16640)
-- Name: text config_pk; Type: CONSTRAINT; Schema: config; Owner: -
--

ALTER TABLE ONLY config.text
    ADD CONSTRAINT config_pk PRIMARY KEY (key);


--
-- TOC entry 4776 (class 2606 OID 16647)
-- Name: number number_pk; Type: CONSTRAINT; Schema: config; Owner: -
--

ALTER TABLE ONLY config.number
    ADD CONSTRAINT number_pk PRIMARY KEY (key);


--
-- TOC entry 4778 (class 2606 OID 16656)
-- Name: proxy proxy_pk; Type: CONSTRAINT; Schema: config; Owner: -
--

ALTER TABLE ONLY config.proxy
    ADD CONSTRAINT proxy_pk PRIMARY KEY (id);


--
-- TOC entry 4780 (class 2606 OID 16658)
-- Name: proxy proxy_unique; Type: CONSTRAINT; Schema: config; Owner: -
--

ALTER TABLE ONLY config.proxy
    ADD CONSTRAINT proxy_unique UNIQUE (link);


--
-- TOC entry 4762 (class 2606 OID 16483)
-- Name: cache cashe_pk; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".cache
    ADD CONSTRAINT cashe_pk PRIMARY KEY (id);


--
-- TOC entry 4764 (class 2606 OID 16490)
-- Name: cache cashe_unique; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".cache
    ADD CONSTRAINT cashe_unique UNIQUE (user_id);


--
-- TOC entry 4758 (class 2606 OID 16460)
-- Name: keys keys_pk; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_pk PRIMARY KEY (id);


--
-- TOC entry 4760 (class 2606 OID 16474)
-- Name: keys keys_unique; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_unique UNIQUE (key);


--
-- TOC entry 4754 (class 2606 OID 16410)
-- Name: users newtable_pk; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".users
    ADD CONSTRAINT newtable_pk PRIMARY KEY (id);


--
-- TOC entry 4756 (class 2606 OID 16470)
-- Name: users users_unique; Type: CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".users
    ADD CONSTRAINT users_unique UNIQUE (tg_id);


--
-- TOC entry 4770 (class 2606 OID 16620)
-- Name: games games_pk; Type: CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.games
    ADD CONSTRAINT games_pk PRIMARY KEY (id);


--
-- TOC entry 4772 (class 2606 OID 16588)
-- Name: promo_translate newtable_pk; Type: CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_translate
    ADD CONSTRAINT newtable_pk PRIMARY KEY (id);


--
-- TOC entry 4766 (class 2606 OID 16694)
-- Name: promo promo_pk; Type: CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo
    ADD CONSTRAINT promo_pk PRIMARY KEY (id);


--
-- TOC entry 4782 (class 2606 OID 16668)
-- Name: promo_prizes promo_prizes_pk; Type: CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_prizes
    ADD CONSTRAINT promo_prizes_pk PRIMARY KEY (id);


--
-- TOC entry 4768 (class 2606 OID 16706)
-- Name: promo promo_unique; Type: CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo
    ADD CONSTRAINT promo_unique UNIQUE (check_id);


--
-- TOC entry 4785 (class 2606 OID 16484)
-- Name: cache cashe_users_fk; Type: FK CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".cache
    ADD CONSTRAINT cashe_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4783 (class 2606 OID 16626)
-- Name: keys keys_games_fk; Type: FK CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_games_fk FOREIGN KEY (game_id) REFERENCES promotion.games(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4784 (class 2606 OID 16461)
-- Name: keys keys_users_fk; Type: FK CONSTRAINT; Schema: hamster-kombat-keys; Owner: -
--

ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4787 (class 2606 OID 16695)
-- Name: promo_prizes promo_prizes_promo_fk; Type: FK CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_prizes
    ADD CONSTRAINT promo_prizes_promo_fk FOREIGN KEY (promo_id) REFERENCES promotion.promo(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4788 (class 2606 OID 16674)
-- Name: promo_prizes promo_prizes_users_fk; Type: FK CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_prizes
    ADD CONSTRAINT promo_prizes_users_fk FOREIGN KEY (winner_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4789 (class 2606 OID 16679)
-- Name: promo_prizes promo_prizes_users_fk_1; Type: FK CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_prizes
    ADD CONSTRAINT promo_prizes_users_fk_1 FOREIGN KEY (owner_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4786 (class 2606 OID 16700)
-- Name: promo_translate promo_translate_promo_fk; Type: FK CONSTRAINT; Schema: promotion; Owner: -
--

ALTER TABLE ONLY promotion.promo_translate
    ADD CONSTRAINT promo_translate_promo_fk FOREIGN KEY (promo_id) REFERENCES promotion.promo(id) ON UPDATE CASCADE ON DELETE CASCADE;


-- Completed on 2024-08-20 03:22:01

--
-- PostgreSQL database dump complete
--

-- Completed on 2024-08-20 03:22:01

--
-- PostgreSQL database cluster dump complete
--


PGDMP  &    %        
        |            postgres    16.3    16.3 #               0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                      false                       0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                      false                       0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                      false                       1262    5    postgres    DATABASE     |   CREATE DATABASE postgres WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'Russian_Russia.utf8';
    DROP DATABASE postgres;
                postgres    false                       0    0    DATABASE postgres    COMMENT     N   COMMENT ON DATABASE postgres IS 'default administrative connection database';
                   postgres    false    4892            �            1259    16478    cashe    TABLE     �   CREATE TABLE "hamster-kombat-keys".cashe (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    welcome bigint,
    loading bigint,
    report bigint,
    process boolean DEFAULT true NOT NULL,
    error bigint
);
 (   DROP TABLE "hamster-kombat-keys".cashe;
       hamster-kombat-keys         heap    postgres    false            �            1259    16477    cashe_id_seq    SEQUENCE     �   ALTER TABLE "hamster-kombat-keys".cashe ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".cashe_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            hamster-kombat-keys          postgres    false    225            �            1259    16451    keys    TABLE     �   CREATE TABLE "hamster-kombat-keys".keys (
    id bigint NOT NULL,
    user_id bigint DEFAULT 0 NOT NULL,
    key text NOT NULL,
    type text DEFAULT 'KEY'::text NOT NULL,
    "time" bigint DEFAULT 0 NOT NULL,
    used boolean DEFAULT true NOT NULL
);
 '   DROP TABLE "hamster-kombat-keys".keys;
       hamster-kombat-keys         heap    postgres    false            �            1259    16450    keys_id_seq    SEQUENCE     �   ALTER TABLE "hamster-kombat-keys".keys ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".keys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            hamster-kombat-keys          postgres    false    223            �            1259    16412    promo    TABLE     �   CREATE TABLE "hamster-kombat-keys".promo (
    id bigint NOT NULL,
    name text NOT NULL,
    "desc" text NOT NULL,
    link text NOT NULL,
    check_id smallint DEFAULT 0 NOT NULL
);
 (   DROP TABLE "hamster-kombat-keys".promo;
       hamster-kombat-keys         heap    postgres    false            �            1259    16411    promo_id_seq    SEQUENCE     �   ALTER TABLE "hamster-kombat-keys".promo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".promo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            hamster-kombat-keys          postgres    false    220            �            1259    16420    subs    TABLE     v   CREATE TABLE "hamster-kombat-keys".subs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    promo_id bigint
);
 '   DROP TABLE "hamster-kombat-keys".subs;
       hamster-kombat-keys         heap    postgres    false            �            1259    16400    users    TABLE     !  CREATE TABLE "hamster-kombat-keys".users (
    id bigint NOT NULL,
    tg_username text DEFAULT '-'::text NOT NULL,
    tg_id bigint DEFAULT 0 NOT NULL,
    ref_id bigint DEFAULT '-1'::integer NOT NULL,
    "right" smallint DEFAULT 0 NOT NULL,
    lang text DEFAULT 'en'::text NOT NULL
);
 (   DROP TABLE "hamster-kombat-keys".users;
       hamster-kombat-keys         heap    postgres    false            �            1259    16399    users_id_seq    SEQUENCE     �   ALTER TABLE "hamster-kombat-keys".users ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "hamster-kombat-keys".users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            hamster-kombat-keys          postgres    false    218                      0    16478    cashe 
   TABLE DATA           e   COPY "hamster-kombat-keys".cashe (id, user_id, welcome, loading, report, process, error) FROM stdin;
    hamster-kombat-keys          postgres    false    225   +                 0    16451    keys 
   TABLE DATA           S   COPY "hamster-kombat-keys".keys (id, user_id, key, type, "time", used) FROM stdin;
    hamster-kombat-keys          postgres    false    223   L0                 0    16412    promo 
   TABLE DATA           P   COPY "hamster-kombat-keys".promo (id, name, "desc", link, check_id) FROM stdin;
    hamster-kombat-keys          postgres    false    220   �L                 0    16420    subs 
   TABLE DATA           D   COPY "hamster-kombat-keys".subs (id, user_id, promo_id) FROM stdin;
    hamster-kombat-keys          postgres    false    221   �L                 0    16400    users 
   TABLE DATA           ]   COPY "hamster-kombat-keys".users (id, tg_username, tg_id, ref_id, "right", lang) FROM stdin;
    hamster-kombat-keys          postgres    false    218   �L                  0    0    cashe_id_seq    SEQUENCE SET     K   SELECT pg_catalog.setval('"hamster-kombat-keys".cashe_id_seq', 317, true);
          hamster-kombat-keys          postgres    false    224                       0    0    keys_id_seq    SEQUENCE SET     J   SELECT pg_catalog.setval('"hamster-kombat-keys".keys_id_seq', 701, true);
          hamster-kombat-keys          postgres    false    222                        0    0    promo_id_seq    SEQUENCE SET     J   SELECT pg_catalog.setval('"hamster-kombat-keys".promo_id_seq', 1, false);
          hamster-kombat-keys          postgres    false    219            !           0    0    users_id_seq    SEQUENCE SET     K   SELECT pg_catalog.setval('"hamster-kombat-keys".users_id_seq', 368, true);
          hamster-kombat-keys          postgres    false    217            x           2606    16483    cashe cashe_pk 
   CONSTRAINT     [   ALTER TABLE ONLY "hamster-kombat-keys".cashe
    ADD CONSTRAINT cashe_pk PRIMARY KEY (id);
 G   ALTER TABLE ONLY "hamster-kombat-keys".cashe DROP CONSTRAINT cashe_pk;
       hamster-kombat-keys            postgres    false    225            z           2606    16490    cashe cashe_unique 
   CONSTRAINT     _   ALTER TABLE ONLY "hamster-kombat-keys".cashe
    ADD CONSTRAINT cashe_unique UNIQUE (user_id);
 K   ALTER TABLE ONLY "hamster-kombat-keys".cashe DROP CONSTRAINT cashe_unique;
       hamster-kombat-keys            postgres    false    225            t           2606    16460    keys keys_pk 
   CONSTRAINT     Y   ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_pk PRIMARY KEY (id);
 E   ALTER TABLE ONLY "hamster-kombat-keys".keys DROP CONSTRAINT keys_pk;
       hamster-kombat-keys            postgres    false    223            v           2606    16474    keys keys_unique 
   CONSTRAINT     Y   ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_unique UNIQUE (key);
 I   ALTER TABLE ONLY "hamster-kombat-keys".keys DROP CONSTRAINT keys_unique;
       hamster-kombat-keys            postgres    false    223            l           2606    16410    users newtable_pk 
   CONSTRAINT     ^   ALTER TABLE ONLY "hamster-kombat-keys".users
    ADD CONSTRAINT newtable_pk PRIMARY KEY (id);
 J   ALTER TABLE ONLY "hamster-kombat-keys".users DROP CONSTRAINT newtable_pk;
       hamster-kombat-keys            postgres    false    218            p           2606    16419    promo promo_pk 
   CONSTRAINT     [   ALTER TABLE ONLY "hamster-kombat-keys".promo
    ADD CONSTRAINT promo_pk PRIMARY KEY (id);
 G   ALTER TABLE ONLY "hamster-kombat-keys".promo DROP CONSTRAINT promo_pk;
       hamster-kombat-keys            postgres    false    220            r           2606    16424    subs subs_pk 
   CONSTRAINT     Y   ALTER TABLE ONLY "hamster-kombat-keys".subs
    ADD CONSTRAINT subs_pk PRIMARY KEY (id);
 E   ALTER TABLE ONLY "hamster-kombat-keys".subs DROP CONSTRAINT subs_pk;
       hamster-kombat-keys            postgres    false    221            n           2606    16470    users users_unique 
   CONSTRAINT     ]   ALTER TABLE ONLY "hamster-kombat-keys".users
    ADD CONSTRAINT users_unique UNIQUE (tg_id);
 K   ALTER TABLE ONLY "hamster-kombat-keys".users DROP CONSTRAINT users_unique;
       hamster-kombat-keys            postgres    false    218            ~           2606    16484    cashe cashe_users_fk    FK CONSTRAINT     �   ALTER TABLE ONLY "hamster-kombat-keys".cashe
    ADD CONSTRAINT cashe_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;
 M   ALTER TABLE ONLY "hamster-kombat-keys".cashe DROP CONSTRAINT cashe_users_fk;
       hamster-kombat-keys          postgres    false    225    218    4716            }           2606    16461    keys keys_users_fk    FK CONSTRAINT     �   ALTER TABLE ONLY "hamster-kombat-keys".keys
    ADD CONSTRAINT keys_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;
 K   ALTER TABLE ONLY "hamster-kombat-keys".keys DROP CONSTRAINT keys_users_fk;
       hamster-kombat-keys          postgres    false    218    223    4716            {           2606    16430    subs subs_promo_fk    FK CONSTRAINT     �   ALTER TABLE ONLY "hamster-kombat-keys".subs
    ADD CONSTRAINT subs_promo_fk FOREIGN KEY (promo_id) REFERENCES "hamster-kombat-keys".promo(id) ON UPDATE CASCADE ON DELETE CASCADE;
 K   ALTER TABLE ONLY "hamster-kombat-keys".subs DROP CONSTRAINT subs_promo_fk;
       hamster-kombat-keys          postgres    false    220    221    4720            |           2606    16425    subs subs_users_fk    FK CONSTRAINT     �   ALTER TABLE ONLY "hamster-kombat-keys".subs
    ADD CONSTRAINT subs_users_fk FOREIGN KEY (user_id) REFERENCES "hamster-kombat-keys".users(id) ON UPDATE CASCADE ON DELETE CASCADE;
 K   ALTER TABLE ONLY "hamster-kombat-keys".subs DROP CONSTRAINT subs_users_fk;
       hamster-kombat-keys          postgres    false    4716    221    218               ,  x�]W�q%9;���IQ�$6�9;�Ϳ�<Ol_P�֓D� ([��V>#������?����z<�{��>K��㹰����YϜ������l܄}F�]Wl��m�(|��5���{Oa���3�h��잶pI0��c��47?����c�憹�;,��_#���M��:x�6�$�w�����H�7!|�r�m	o�֐j��0�K�$�5���dl^e�:\xxJR燒s��Q�Xr� �(
�%��]���U�K�Dn�xߌ��Z�X�Tܚ���sjօ�>�+�1��@�<XAQ�q+)#�Q�]Z�M��� ϐ[���&G��M�WkB��}��y�5�j�]�dcM��WO��������=�������� |�r�h�ɹZ�w9��k�(n�
�p�8E�c�fٷa����`�[T)ԪB�%�2ka�ǌ/�ūDҰ'Y�[XT�!�����,NimƉ��z�ir����0�)� � k���U2Z��
"��V�X��,��e��~�X��B$M��ld��b���BXJC����u��	>%g۔:����3��:X}�45�/�Bd��|�@��|R����1���.κ@OG[5e��D��'u7Bp�1ӗ�ͬ�'j�E��g:͓&,N�py�)���>���F��`��8-��œ<���Y�*�c��{��s|���{������a��T\��QH�j��:l6`݇ԣ]��G!����ڤ��A�o�:��ƅRN5=�>����;�<4��ڤ��O;��,��yu�؁�q���Zta�v���im��ڤ=m)z�"=ȕ�q��q�����N>">kH�Yմ��	�t�,��n�#��'��Ѝ]J�G�#��i&fqjǘ�%�T笯*��Në.�W�䉏��X��)��~���8F�/���æ�kr�fz	u�k�P`�Y���,(�3R/���V��G���&#���%<��0���,龨0�X)�M���r&x�(���ڀN�ψ�D[���Nw�!e�b���\0�����:�J��dQGV��l4�S�Η�1-�K��+�!q�_DC�����B [!,����'��d��	�>�\o����և���<�{z�8���e�x�>|A�*�ڰ�> 9��qތ���J1=�?�v���{X�f&*~6,j�����q/ʋ��q�CB�k�$4T�^��u�v�.��Ă������0�p��w�Q?�L�dzI �s\r�2e��q1��U������i��������?�;�            x�][ٲ�:�}��_�C3ң�ʴic(��Ϩ��Z)��"n�`m�r�,������Ww#1=�	o����OJK'���G:��O�˿z�SM�v	�:jg���@�ی�����0$���m�������W���'4���$��]�g���
���^,��_!S�#�J2�?k�Lj��>��PR���erƅ�}�=AB���$��J�S�O(B�6"�_Q�O��ԏ�J��?�����/����]&��+>����,�?�k�>�8��������*����Nǿ����)௾`+3{��!�ދ����|/gI�. �}6����{���߻��X��(<�T��l!F$��_0�H��Z;�p���O�"	��3"�O$�i#�YA��jH�*���:���������Ǚ���}�|�!,ѡ�"�r
^��ޚ\�"i�?�Z��$ �:��ކ��k��,��⣁�$�g�\x�5՝8Kd���{��S1Y��7��������ߟ�s��z��>d6�pCD�/BL-=��
��#�Ş#TP#��@�˵&!�]�>[)X|D�Ol+P��x�m/*Z�������M!G��ѳ��~$B��I���_���/�E`�����0J�Br�+�?�D�,�9p�&��G/(�^H6RsE��I��H�e9���|�H��b򴷷���h����p�D��;{iv���2���'"�)e����#����vc=$���R!��ш�U7�ز�q���$F�	�����n��"Ŭ6�,}�(���I1��[#P���I4	�aw#�/�7<"  �D�����I�=Rg��"$��������-���1���P_j{D�WA>�#�Ɵ����E�M��inX����:�@<���P�L㡌��J7��3�}���y��(���H�-�$bVFDH�	nݰ#��D��2=Tˆ�VH�i�X���u���D��9A���$���8��EX{j&�Ju�.��=J�$��0�%�G�$�r�j� �G������n������)Q�[$��m~B�kX���N�Q3\���)����:�+"d	m�A�Ӷ�<nu�H�ʯP\+�B�m �j2�LJ>�3�<�Tr�����py� "�؉���X����%KW b�)D�ěC:r~G��mM��yx���g���L������!s�CЄ(4`���2���Sw��)�����By��C;�z!Q��}��5Q(��,ԻvT��H�Ӵf��f8���Po�*��q�+.�@��Mu��%�A�X��r���� ,T���o4�� -0�.?#B�	�>bТmuK� �m'�U[@�rP/ �O���Er⤅�5R��RmI}��Z8��(�A�B�K���C�Yw���b��<�a��5��L�yL���-e����s�y�Re�v6��h�w�R�^м�:���s����I,��:uӀu�?���h!s>��ۂ��Wn�BD=�9HԴ��Y�����ɛ_�t�[����L�P��td˜�
��`���~CX�VP7��׿�
ѼG�؊�H��������G���N�*ptʽ�6���^� 1ޟ袅lgz->�Q$]�	�����؍/���"S8:�8� y"GF��]��~����	�D�׽ W�T@�R��Gr���5\�������4M��Z7}eVD��6�X��~��Kquy���e3Ҳ�9�����)�����O�=k�H��5��U��ږ������#9�Vv����O��Tk�G�����ʙ�����@<��^6�J�
��'vu����L��A��^Q��=Ȩ�	g6�i���#��lt����<n�]�Pi�s�G��&*��A�S��,�]���.��!Vͼ{�����}�$s��X
��	H�7`���aZ��<�8�$��K���C�In��'z��r)�͌�-��Sy���D9�e���Q]���c�-�ρ�[V�d� ��O#)=��~���,������8蠦�f2Dh�����UcB���g��:؟%��� �P:RVL*�H��y��PNG�15� ��F�ѽ������l?j*{��ǝ��e�"Ne:�N�3��8�6*�"&f�I�w	д���,.YN7X�+�-��n�a��(3;y�-����b���l12���6��'�3�]*t����P��3BJԳ�Sm���������t4.��$ڑ}�g����H!�b@��<~�5��h.�,ЅL �=�]r�5�@Ϸ乇�>R��B{���Rq�WQc����Jg�)1M��G��}4���~}��BO�����Ngb�"�0��ǻ 
�<X ��9Ǖ�]��I(=u4;O�$�5�P<Ͱ?�	�d;�J��\Ѵ�H�6m|뀠VbJ�r��s��{-m�`�*���rƪ
�{]��HĖ�_'�王�M�h3k�"D��xszE�f4��;�gȬeeԃ�-�?=��3P0=�C.�����_#{�3#sI���޸�0�������qE(ΨL���Z�"VXãu�%cE�}E�67�g���sͣu>�(0�Ԩ��s"S��70
p�<�eE���l��۳���2��fą�j�b�\��έ���̠��� �Yqm��u^AH�TI� ��bj��#�f �U޸J�o�h�V����k3�I� ��A|8�!��:<j�μH<C���ʱ����5�,��K��c�w�3�K�sM.�o�E��4w����ʍl*�p�!^�(���{�BC�����-5K.����wJ�OcoH-��<z�f!��Q1�e�	�������r��v
�N�]a�-W�J47�S@�)e ��lE�9�4�HܟY� D%����~�v��=�%��NI�O��{���a�h��"cso0�}!�7�w��@�C�I}.h�>���=��.U��՗o�+�#߬]jH'vX�v�?���$��͋��7���9?%��r�S`���D�q���[^q�J�������3=���"�@�I0��K��������O�F��?��eR���iU�TG��S��`W�rE_:^�/$fj�Wf���b��b����ŊsN2A�Lׁ�oCNF�Y�9�§��E��@϶�9%n��YV",ێw�H���?��3'�ynY&����E,�����'�8,��N��u�'`L���
�<yY�h	��h!�)�8��Tٺ���@���ûQ���[�=�������۳`c}���؆�C�JN���0[�����|͜�2�
�b��r@,U��㬜М�~ ��P�F�����˖�Mm0��>�}��K5 1�e)wy��Z��Gł��M�Q����e�r@�@���+Rr�5f���Ҽ���/@a�l��_+�ͬ��EJ-����݋Z�������2����<W.�v�y�0��U��2�pA���.��������	A��V�(һd_��6�����:�7oY���ŕ�M���Q?_?����5+�ȷyѾjZ圝`���8E��[�����	���,w���Qˇh�y��ѳ_~B05� n��> -5����&w���>N��B�{SIk�Q�<i�Lu_�0錤���,ᾁi�b2�}��,�#���H���r�4N6?!vu�k�-$���q|M4�.�"�9Q9��|�g�+��A	�����]^�@�T���c@��WwWI���x}.2Zo��#�c;3)����A�#�c���tWd���]�A��Z����k��P�S(�Z�!Oگ�3*^Wz>�5'B<v���ߥ��8 �2͗� 4��&*��1������q�����X�0�;~��7Bۃ�:[LN����Z��5��n�1$�9�%�"݇�
RC�~/~.�dQ$Z@I� �G�W�8�,�,/B�g��4 �M)�oPT�C���6�'��,�H�;�G��oa�2�ۖ}qp޸N���'�H�Fk�����ɭ������b
��F� |_�T�O\��2�S&����/�ԱS�%�X7�bX�ܰ^��6|][p�=:4P�ҵr@��vR�E�|C�Xw A  d�5�|j��)��d����.%9��=�]R�u�W7EsCS="^77�H�����HniJ��_T�{0qg-r���&�_���I�lr@��X_ޟM��#o���ۖ��:� �̊�|Y�k���YT9 E7-ߑޒ�-_o���K�����*UMY�][�eN7�)����}��E�\לS�G(~`U;	��}��Rf�"c4`<|�x�+���⏷%x��_{�����ʂ�r�6� _�c<c��.�D�a�4M~!n�����W!����nuM!.�,�4�\x^+^�.�mFfA�5�g���=�t�x������D��F�����B��1 �Ԃ�S3o�>jkTƵj�t4_3v
2y�W���}9��|�o��I(w�X�<�C���(�QA�)�]qλ��4Z<ME�t2��j!0�����a^3-t�r������'�_Wu˄J��Ƃ�C��pΰ���i����-e?��GEUh4yc7ö�̷���t�������:"Q.=-όp��W���'�g~;�W�����PVF#�>�>S&�Ѥ���x�oyyS|��D�������va���w��~�O����Kv*�v�����Q�RH/@�f-��z�p�y����Lm��MT*|j��J
�Z�����ًh�c��m�̰�:%� �,��7��䨬=ܭ�{�1m(R=�*���3��wq�y�Q]d/q̵ЅM�����C\M��j{s2-�|���m"_��i�HgدPr�h�<Ȇ���G�|�žx��߈�
?�>&�/�'�/k'��h���PB�$�?��h�W��
���� 2�C�����h��X�xK�MIJ�ԕq���]��q���dv�J���w�uCC�?��+��� 
@"N��G~�Ψ���Fd'�j��k�G��j�i�@��ε0�~���g��rE*���e�V�^7�pz��oN�7��X�]3=�I���cj-Ho�'_I���sFJ&h��qu���j�냆�ggX���Z|f������Wt��m���9!OB�c��'�8,#�׏P.��8^1B�Rwh�۵#���E|��3�ٸ&��ŕ�Rhu~�I,��`��ʽ�Gx��l �1���Ʈ�45W)�j
S�-�zH� ��<z����ׅf�.�5�"R�C{�g��#si�!]C&���y�l8n<�uY�W�r��Zs�Q��8Y��[]&~`�`(ۻ�Ĕr���j�^���+�W���ީ8d
�#y'�NM��v�_�{&���x�r��-�o�zT�v�m�޶B(��z�M�6�ԡ��9����������d�-���*s�7�N�	�z>V�Zt$�W�|�� �d\���Tw\����7��|���c�ar�Neר	[$q�s�>���.�J��z��>!���:�Ȼؔ��^wH�9_IiR例�{ԭ��U�)Y��T*�U@�ϳ�n�_魄?���z8Ŋ~^2��X��ZWzs�&8��:����w$%����x)�:i!VA�)�q��as-�S[^o|� Bu+Q����GQ���%�fD�a�-]~�5I,�ԏ�ly�~�p�&�h/�ȵ>)�2=d���]�k~��w[N����LW���&���p�Go�±0�|�/`�F��tE�.�Н
_H ov�h��N���qW��e�ʂw4�xQ��?zċP�e��7[�!��C��d��G�8j9��q�WOU��X��SV�dZ51ɝ���ع��Ö����&�c^�n�R�������H��3?��P �+FSq�/��OB��� �����Ɗ�&W=�d�"FVb]�b/���SO�Y+�B�A�D���1�V���%�C�(1vuHz�v����"V��~�N�qs�0�i����{p�h��e�"�/��O߳z���1��a�r@l���k'��e/\dM�5�+gC�`7�r}<�e��m`���=?#��8���Nz]@n�o�P�U�T��s^��{	;�֠�s�AV_3;�Lg�W$6��Y�s�^1	�'�0�����6,;��dC�d�<3 I��'Ki�®���`���9ļ�>?�Ӌ�bD��?�g�}Jq+N�,^u�)0d��e�oϘ}>z�b�Z��3����lXu"�X� ߧW��p�I]���qqզ>	ޓ1
j��� q�v֜���+iׂE*СF��L��-\~<�V�U��ت3E�I�2Jޏ�!��(�%��:3�(Na�~��V
��Q������@��*��3�z�?�d��u�B�sU����v[��a��(#u9�jt6��@R��qs���4S����)�Gv���N
1�#^��^d-��)�]���+]Ľ�o��~R#���9�l��ĦVڥ��č�s�[g���n(���Ҟ�t2 M��Ǡ�a�k~V�	���3=�L���� ��Rbvb�G��yz��?��V˨ū�970�Ï6�*|����T����A��I;^��x�ң�L����ɧ--ⵥ+�Ɂ8�ڞ+rC���� T�(tUs]j�r�� �6wߛ���0��-�l~x�L�ޜL��.��A�l�!*nqj�$r�)n5'SIC��O�����}�����B�??�tB����$������9�i�<��_����gq7�+���_�q[�>$���k����4��3R:yq��ww@ҁ�^��TJ&^��O���=b�h��@�«�S�P+��G���"������J��Br�T�GI���Nޜ�C�������*>P�"W����:�C<��p˶O�=1b��5��VnO���3�.���\6��{��^D�GZx;�9�1���̆<�L�r-���7��[2-�'
 ����� Q5^$wT�F�*O&�B��n��G�h7��64mu�䀸kth��g�G� J�J���%Y�4����A߭�#s��b�kB�!i׸���d��NH�}!�ן3R/N5\.O��e����O��4����[��B�Ļ'��4bP�bʆ)"-�'�ڢ,(�����x��{�Xޚ@��se*�,�����CB��Moƹ��O@�_��|�~�_�4��B c��:s9{Ұ<r@��,��_�e"琹�6jT�)��?�������2S
v            x������ � �            x������ � �         z	  x�UX�r�:|F>f
���ę,�vR���ܚ*d�"�MI���OC�����OwÜ
���MXh!�SZ+E(�����\���Q�
�g�m�h������Z��f�ሷe�����O�f��A'%��AS���2b�8~u�!߻e�9.)����k����M����m?�-T[�͟-iy�%��>E¸��j�ގf�l��ĴxN��\�yYg�/G�-�(b(����KhJ��Cq������Xn���LPҴ�&���ya�F<� �D��~����M���9gi�B��8l��X�D��F���ۺbdj�ɧ:v��e�/�HrՅ?��.��Q%���"~��>�{N�|��kM��	!�:�2LJ�);,y���r����JJ�En2~�"�*�d�β���85�0�Q�K���oÒPED��P^�%%yX�/�G��x���|Cއ��� �$S��ʹ��{߄.����(c���k[��d��O~�}�	�o��R˷-N��eo���3e�qY��=l{4�Kg���� f+�����4U1�Rk�n�D\�,a<T|�YZ�U�:
�3��-�#T�8k�$C>�c�~<YeQ��;�D�4F~zJq?�J�,Z�tԕ#,���X?�j�G�5 ~��8��oN��}~A��e�;E��U���pj9�R�� �\hdiFCTz��\����$�D�d���
 ��6Ͷyn�udQ��GnǞ��C�p;�iY��9�46>noS+ُK�'_�i��#������S���WF�ih�� �� ������ͼ�.+[,y�q��)�hG=!�*#G�Z������eـ�08S��{�m��
������d���Z	�+�����}�J�F9*�p��Й��]ئ�.n��(Q|^@n@A�_�~�\]c©n�+������4�DA�	�bb�vT�Ƨ�'̂j���$��2-��nt���b�\��w�v����-׺ ���o�#�՞d��Y'K���Ԣ��X�W�
�BL�b�[�]�fL#����B�.]�Sπ� ,cu	��t�șb�]A��L������F�<������m������#d��&1f�(w��F[1# {� ��2C��z�v!�PA�lp'�x�H����t�rp���������O��n�Uά�>|����_�(��s�%M���.��0$t��H�U��g���pYn��\,��M�yA����]Q8���t�@�%��\P�&̼%R8# �2��5��7Ub���������v��P/ӌ�ws��`m�)d��k��t�_�l���(���x_a��	���:Uj������#H�K�LĊ��;���-3T"��J%}�nܞ�[�����|<��x���!�lp.����䟺0�ǥ�3�=-~�������B�]�`����Ԝ���e:� /�+r�T����:ДR������ ���Ph��-�������PW��?�p+����Z����4�7�g(f�,"	z��N�y<�~_�� <'/����_&nbB��K���-�|������([�r�@uj'��po�P%y��-���\���M8ƹi1���JЌ+m D7�I��&��(��Q�,1fJ�ԁ'*L��J�o�Ѿ�7ؑ��	/F�
�`
�.�o�2R������ރHA��|��ӡ��7��u��pu4�9r��%?0~bN2��1��Gvϡ���w��u��z��8�93
�ܙ���w��h�ZC�L&e]6P�.`��`鹗
8�zI-����N[��
��|�F�G�B�_F0=�x�ۇ�+`�*�P��4����=��$�\s�����^6I��ob�9�|���e]��J�
u�<�i��`�9Z0u�O�6#[�2X�<�OL��W��fƧ\.W�8�?����C�� O^*	oz�hǩ��0s�l'%?j�'?���UU4;Pm����Z��Ld�%\4X��TswS���������dǋK�c�H_��5��#����X�zy	PS�O��4s-z���49b�t �v��fO�LI��O�2?Om�Y�(/�C�}:��,�]�й�e<�s����2_Ȭ��`z�m�s�����U|0-`���d$�lJ��I  �e
鷅�4�����f�!`���{L:�84��R�1e�<�@��c�qws��_w�Ŕ�凌.mh_}��X[�@�<%(|u��D��6�Te�T�?g\����}�����r �Ei��c�<g��A�g�/Em���|���e�Z߯��>�l�y9tq�a�0�P	�����:�����Wutx4KS@	���uꎯ3>�]v���޽�/��6�     
###
BCC
###

This version of PgBouncer allows you to configure BCC
connections (Blind Carbon Copy, as in email) along with the
usual connection. When configured, the corresponding
postgres instance will receive all the same input as the
main instance. The output of the BCC instance is ignored.

::

 ┏━━━━━┓     ┏━━━━━━━━━┓ host:port ┏━━━━━━━━━━━━━━━┓
 ┃ app ┠─────┨ bouncer ┠───────────┨ main postgres ┃
 ┗━━━━━┛     ┗━━━━┯━━━━┛           ┗━━━━━━━━━━━━━━━┛
                  ┆                ┏━━━━━━━━━━━━━━━┓
                  └╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶╶┨  BCC postgres ┃
                 bcc_host:bcc_port ┗━━━━━━━━━━━━━━━┛

The input duplication is performed on a level lower than the
postgres protocol. Every time PgBouncer opens a new
connection to the main postgres instance, it records the
login sequence and creates a buffer for the input. PgBouncer
also opens a connection to the BCC instance.

When the BCC connection succeeds, it is fed with the
previously recorded login sequence and with the buffered
input. After that, PgBouncer continues sending the input to
both instances, buffering it if the BCC instance is unable
to keep up with the main instance.

If the buffer grows too large because of the BCC instance
being slow or unresponsive, PgBouncer closes the BCC
connection, clears the buffer and tries to reconnect.
These reconnections are attempted periodically.

pgbouncer.ini
#############

Per-database settings
=====================

bcc_host, bcc_port
------------------

Set ``bcc_host=`` and ``bcc_port=``. The "blind carbon copy"
connection will receive all the same queries and ignore all
the results. It will not disrupt the main connection and
will disconnect if it is slower or anything else goes wrong.

Generic settings
================

bcc_connect_timeout
-------------------

If connection to a BCC server won't finish in this amount of
time, the BCC will be skipped. [seconds]

Default: 1.0

bcc_reconnect_period
--------------------

How frequently to try reconnecting to skipped BCC servers.
[seconds]

Default: 10.0

bcc_buffer
----------

The size of the BCC buffer to accomodate lagging. [bytes]

Default: 1048576

Example
=======

::

 [databases]
 postgres = host=127.0.0.1 port=5432 dbname=postgres user=kvap bcc_host=127.0.0.1 bcc_port=5433

 [pgbouncer]
 listen_port = 6543
 bcc_buffer = 3145728
 listen_addr = 127.0.0.1
 auth_type = any

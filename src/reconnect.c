#include "bouncer.h"

static struct event ev_reconnect;

static void serverlist_reconnect_bccs(struct StatList *list)
{
	struct List *item;
	statlist_for_each(item, list) {
		int i;
		PgSocket *server = container_of(item, PgSocket, head);

		for (i = 0; i < server->sbuf.bcc_count; i++) {
			SBuf *bcc = server->sbuf.bcc + i;
			if (!bcc->sock) {
				slog_warning(server, "reconnecting bcc #%d\n", i);
				dns_connect(server);
			}
		}
	}
}

static void reconnect_bccs(int s, short flags, void *arg)
{
	struct List *item;
	struct timeval period = { cf_bcc_reconnect_period / USEC, cf_bcc_reconnect_period % USEC };

	statlist_for_each(item, &pool_list) {
		PgPool *pool = container_of(item, PgPool, head);
		serverlist_reconnect_bccs(&pool->active_server_list);
		serverlist_reconnect_bccs(&pool->idle_server_list);
		serverlist_reconnect_bccs(&pool->used_server_list);
		serverlist_reconnect_bccs(&pool->tested_server_list);
	}

	safe_evtimer_add(&ev_reconnect, &period);
}

void reconnect_setup(void)
{
	struct timeval period = { cf_bcc_reconnect_period / USEC, cf_bcc_reconnect_period % USEC };

	evtimer_set(&ev_reconnect, reconnect_bccs, NULL);
	safe_evtimer_add(&ev_reconnect, &period);
}

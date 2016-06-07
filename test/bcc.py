#!/usr/bin/python3

import sys
import os
import time
import shutil
import tempfile
import configparser
import getpass
import wtfexpect

def postgres(we, host, port, datadir):
	name = 'postgres %s' % datadir
	we.spawn(name, [
		'postgres',
		'-h', host,
		'-p', str(port),
		'-D', datadir,
	])
	return name

def postgri(we, hosts, ports, datadirs):
	names = []
	for host, port, datadir in zip(hosts, ports, datadirs):
		name = postgres(we, host, port, datadir)
		names.append(name)
	return names

def initdbs(we, datadirs):
	for d in datadirs:
		name = 'initdb %s' % d
		we.spawn(name, ['initdb', d])

	ok = True
	while we.alive():
		name, line = we.expect({})
		assert(line is None)
		retcode = we.getcode(name)
		if retcode != 0:
			ok = False
	return ok

def pgbouncer(we, name, host, port, hosts, ports, database, user):
	assert(len(hosts) > 0)
	assert(len(ports) == len(hosts))

	connstr = "host=%s port=%d" % (hosts[0], ports[0])
	connstr += " dbname=%s" % database
	connstr += " user=%s" % user
	for h, p in list(zip(hosts, ports))[1:]:
		connstr += " bcc_host=%s bcc_port=%d" % (h, p)

	cfg = configparser.ConfigParser()
	cfg['databases'] = {
		'postgres': connstr,
	}
	cfg['pgbouncer'] = {
		'listen_port': port,
		'listen_addr': host,
		'auth_type': 'any',
		'logfile': '/tmp/pgbouncer.log',
	}

	#confile = tempfile.NamedTemporaryFile(mode='w+')
	fd, confilename = tempfile.mkstemp()
	confile = os.fdopen(fd, 'w+')
	cfg.write(confile)
	confile.flush()

	return we.spawn(name, ['./pgbouncer', confilename])

def pgbench(we, name, host, port, database, user, jobs=5, clients=5, seconds=5, init=False):
	params = [
		'-h', host,
		'-p', str(port),
		'-U', user,
	]
	if init:
		params.append('-i')
	else:
		params.extend([
			'-j', str(jobs),
			'-c', str(clients),
			'-T', str(seconds),
		])
	params.append(database)
	return we.spawn(name, ['pgbench', *params])

def psql(we, name, host, port, database, user, cmd):
	return we.spawn(name, [
		'psql',
		'-h', host,
		'-p', str(port),
		'-U', user,
		'-c', cmd,
		database,
	])

def equal_results(we, names):
	results = we.capture(*names)
	retcodes = [x['retcode'] for x in results.values()]
	outputs = [x['output'] for x in results.values()]
	if any(rc != 0 for rc in retcodes):
		return False, results
	if any(out != outputs[0] for out in outputs):
		return False, results
	return True, outputs[0]

def main():
	datadirs = []
	daemons = []

	instances = 3
	host = '127.0.0.1'
	base_port = 5432
	bouncer_port = 6543
	database = 'postgres'
	user = getpass.getuser()
	bench_seconds = 10

	we = wtfexpect.WtfExpect()

	ok = False

	try:
		# --------- prepare

		hosts = []
		ports = []
		for i in range(instances):
			port = base_port + i
			hosts.append(host)
			ports.append(port)
			datadirs.append(tempfile.mkdtemp())

		print("initdb")
		if not initdbs(we, datadirs):
			raise Exception("failed to initialize databases")

		print("launch postgres")
		daemons.extend(postgri(we, hosts, ports, datadirs))

		print("launch pgbouncer")
		daemons.append(pgbouncer(
			we, 'pgbouncer', host, bouncer_port,
			hosts, ports,
			database, user,
		))

		print("wait 3 sec")
		name, line = we.expect({}, timeout=3)
		if name is not None:
			raise Exception("has one of the daemons finished?")

		# --------- bench

		print("bench init")
		pgbench(we, 'pgbench', host, bouncer_port, database, user, init=True)
		if we.capture('pgbench')['pgbench']['retcode'] != 0:
			raise Exception("pgbench -i failed")

		print("bench %d sec" % bench_seconds)
		pgbench(we, 'pgbench', host, bouncer_port, database, user, seconds=bench_seconds)
		if we.capture('pgbench')['pgbench']['retcode'] != 0:
			raise Exception("pgbench failed")

		print("wait 3 sec")
		name, line = we.expect({}, timeout=3)
		if name is not None:
			raise Exception("has one of the daemons finished?")

		# --------- check

		print("check")
		psqls = []
		for h, p in zip(hosts, ports):
			name = 'psql-%d' % p
			psql(
				we, name, h, p, database, user,
				'''
				select tid, bid, aid, delta
				from pgbench_history
				order by tid, bid, aid, delta
				''',
			)
			psqls.append(name)
		equal, result = equal_results(we, psqls)
		if equal:
			print("results are equal: %s" % result[-2])
			ok = True
		else:
			print("results not equal")
			for name, res in result.items():
				filename = '/tmp/%s.output' % name
				with open(filename, 'w') as f:
					f.write('\n'.join(res['output']))
					print("see %s" % filename)

	finally:
		# --------- cleanup

		print("cleanup")
		we.finish()
		for d in datadirs:
			shutil.rmtree(d)

	if ok:
		print("ok")
		sys.exit(0)
	else:
		print("FAILED")
		sys.exit(1)

if __name__ == '__main__':
	main()

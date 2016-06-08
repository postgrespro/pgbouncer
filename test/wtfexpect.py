#!/usr/bin/python3

import select
import subprocess
import time

class WtfExpect():
	def __init__(self):
		self.procs = []
		self.stdouts = {}
		self.names = {}
		self.retcodes = {}

	def run(self, argv):
		p = subprocess.run(
			argv,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
		)
		return p.returncode, p.stdout

	def spawn(self, name, argv):
		p = subprocess.Popen(
			argv, bufsize=1,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
		)
		self.procs.append(p)
		self.stdouts[p.stdout] = p
		self.names[p] = name
		return p

	def getproc(self, name):
		for p, n in self.names.items():
			if n == name:
				return p
		return None

	def kill(self, name):
		proc = self.getproc(name)
		proc.kill()

	def close(self, proc):
		assert(proc in self.procs)
		name = self.names[proc]
		self.retcodes[name] = proc.wait()
		self.procs.remove(proc)
		del self.stdouts[proc.stdout]
		del self.names[proc]

	def readline(self, timeout=None):
		rlist = self.stdouts.keys()
		ready, _, _ = select.select(rlist, [], [], timeout)
		if len(ready) > 0:
			r = ready[0]
			proc = self.stdouts[r]
			name = self.names[proc]
			l = r.readline().decode()
			if len(l):
				return name, l.strip()
			else:
				self.close(proc)
				return name, None
		else:
			return None, None

	def expect(self, patterns, timeout=None):
		started = time.time()
		while self.alive():
			if timeout is not None:
				t = time.time()
				if t - started > timeout:
					return None, None
				elapsed = t - started
				timeleft = timeout - elapsed
			else:
				timeleft = None

			name, line = self.readline(timeleft)
			if line is None:
				return name, None
			if name not in patterns:
				continue
			stripped = line.decode().strip()
			if stripped in patterns[name]:
				return name, stripped

	def capture(self, *names):
		results = {}
		nameslist = list(names)
		for name in names:
			assert(name in self.names.values())
			results[name] = {
				'retcode': None,
				'output': [],
			}
		while len(nameslist):
			aname, line = self.readline()
			if aname not in nameslist:
				continue
			if line is None:
				results[aname]['retcode'] = self.getcode(aname)
				nameslist.remove(aname)
			else:
				results[aname]['output'].append(line)
		return results

	def getcode(self, name):
		if name in self.retcodes:
			retcode = self.retcodes[name]
			del self.retcodes[name]
			return retcode
		return None

	def alive(self):
		return len(self.procs) > 0

	def finish(self):
		for proc in self.procs:
			proc.kill()
		self.procs = []
		self.stdouts = {}
		self.names = {}
		self.retcodes = {}

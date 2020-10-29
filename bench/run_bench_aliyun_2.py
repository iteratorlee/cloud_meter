# -*- coding=utf-8 -*-

from aliyunsdkcore import client
from aliyunsdkecs.request.v20140526.DescribePriceRequest import DescribePriceRequest
from aliyunsdkecs.request.v20140526.CreateInstanceRequest import CreateInstanceRequest
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
from aliyunsdkecs.request.v20140526.StartInstanceRequest import StartInstanceRequest
from aliyunsdkecs.request.v20140526.AllocatePublicIpAddressRequest import AllocatePublicIpAddressRequest
import time, datetime, sys, json
import paramiko

# 查询主机当前状态（初始化中、'Stopped'、'Running'）
def get_instance_detail_by_id(clt, instance_id, status='Stopped'):
	request = DescribeInstancesRequest()
	request.set_InstanceIds(json.dumps([instance_id]))
	response = clt.do_action_with_exception(request)
	response = json.loads(str(response, encoding = 'utf8'))
	instance_detail = None
	if response is not None:
		instance_list = response.get('Instances').get('Instance')
		for item in instance_list:
			if item.get('Status') == status:
				instance_detail = item
				break
		return instance_detail

# 阿里云的账户信息
AccessKeyId = ""
AccessKeySecret = ""

def create_instance(clt, imageid, InstanceType):
	Request = CreateInstanceRequest()		# 创建主机
	InternetChargeType = 'PayByTraffic'		# 网络付费模式
	InternetMaxBandwidthOut = '5'# 带宽
	Request.set_ImageId(imageid)
	Request.set_InstanceType(InstanceType)
	Request.set_InternetChargeType(InternetChargeType)
	Request.set_InternetMaxBandwidthOut(InternetMaxBandwidthOut)
	Request.set_Password('Jd123456')

	start = datetime.datetime.now()

	Response = clt.do_action_with_exception(Request)
	Response = json.loads(str(Response, encoding = 'utf8'))# 正确返回
	instance_id = Response.get('InstanceId')

	# 阿里云需要主机初始化完成之后才能分配公网ip，即需要主机状态为Stopped，再分配ip，否则报错
	detail = get_instance_detail_by_id(clt, instance_id)
	index = 0
	while detail is None and index < 60:
		detail = get_instance_detail_by_id(clt, instance_id)
		time.sleep(0.1)

	public_ip = allocate_ip(clt, instance_id)

	# 启动主机
	Request = StartInstanceRequest()
	Request.set_InstanceId(instance_id)
	clt.do_action_with_exception(Request)

	detail = get_instance_detail_by_id(clt, instance_id, 'Running')
	index = 0
	while detail is None and index < 60:
		detail = get_instance_detail_by_id(clt, instance_id, 'Running')
		time.sleep(0.1)

	stop = datetime.datetime.now()
	startup = stop - start

	inner_ip = detail.get("InnerIpAddress").get("IpAddress")[0]
	return instance_id, public_ip, startup, inner_ip

def allocate_ip(clt, instance_id):
# 分配公网ip
	Request = AllocatePublicIpAddressRequest()
	Request.set_InstanceId(instance_id)
	Response = clt.do_action_with_exception(Request)
	Response = json.loads(str(Response, encoding = 'utf8'))
	if Response is not None:
		public_ip = Response.get('IpAddress')
	return public_ip

def destrop_instance(clt, instance_id):
	Request = DeleteInstanceRequest()
	Request.set_InstanceId(instanceid)
	Request.set_Force(True)
	clt.do_action_with_exception(Request)

def run(public_ip, public_ip2, inner_ip2, threads_num):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(hostname=public_ip, port=22, username="root", password="Jd123456")

	ssh2 = paramiko.SSHClient()
	ssh2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh2.connect(hostname=public_ip2, port=22, username="root", password="Jd123456")

	content = ''
	with open('./run_bench_template.sh', 'r') as f:
		content = f.read()
	content = content.replace('--num-threads=xxxxx', '--num-threads='+str(threads_num))
	with open('./run_bench.sh', 'w') as f:
		f.write(content)

	sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
	sftp = ssh.open_sftp()
	sftp.put('./run_bench.sh', '/root/run_bench.sh')
	sftp.put('./netperf-2.7.0.tar.gz', '/root/netperf-2.7.0.tar.gz')

	sftp2 = paramiko.SFTPClient.from_transport(ssh2.get_transport())
	sftp2 = ssh2.open_sftp()
	sftp2.put('./netperf-2.7.0.tar.gz', '/root/netperf-2.7.0.tar.gz')

	print('sysbench评测中...')
	stdin, stdout, stderr = ssh.exec_command ('chmod +x run_bench.sh')
	stdin, stdout, stderr = ssh.exec_command ('sh run_bench.sh')

	sysbench_result = []
	for line in stdout.readlines():
		if 'total time' in line:
			sysbench_result.append(line.split(':')[1].strip())

	print('netperf评测中...')
	stdin, stdout, stderr = ssh2.exec_command ('tar -zxvf netperf-2.7.0.tar.gz')
	stdin, stdout, stderr = ssh2.exec_command ('cd netperf-2.7.0 && ./configure && make && make install')
	stdin, stdout, stderr = ssh2.exec_command ('netserver')

	stdin, stdout, stderr = ssh.exec_command ('tar -zxvf netperf-2.7.0.tar.gz')
	stdin, stdout, stderr = ssh.exec_command ('cd netperf-2.7.0 && ./configure && make && make install')

	netperf_result = []
	stdin, stdout, stderr = ssh.exec_command ('netperf -l 30 -t TCP_RR -H ' + inner_ip2)
	lines = stdout.readlines()
	netperf.append(lines[-2].split()[-1])
	stdin, stdout, stderr = ssh.exec_command ('netperf -l 30 -t TCP_STREAM -H ' + inner_ip2)
	lines = stdout.readlines()
	netperf.append(lines[-1].split()[-1])
	stdin, stdout, stderr = ssh.exec_command ('netperf -l 30 -t UDP_RR -H ' + inner_ip2)
	lines = stdout.readlines()
	netperf.append(lines[-2].split()[-1])
	stdin, stdout, stderr = ssh.exec_command ('netperf -l 30 -t UDP_STREAM -H ' + inner_ip2)
	lines = stdout.readlines()
	netperf.append(lines[-2].split()[-1])
	netperf.append(lines[-1].split()[-1])

	return sysbench_result, netperf_result

def get_json(sysbench_result, netperf_result):
	pass

if __name__ == '__main__':
	regionid = sys.argv[1]
	imageid = 'ubuntu_18_04_64_20G_alibase_20190624.vhd'
	InstanceTypes = []
	for item in sys.argv[2][1:-1].split(','):
		InstanceTypes.append(item)
	threads_nums = {'large': 2, 'xlarge': 4, '2xlarge': 8, '3xlarge': 12}

	for InstanceType in InstanceTypes:
		threads_num = threads_nums[InstanceType.split('.')[-1]]
		clt = client.AcsClient(AccessKeyId, AccessKeySecret, regionid)	# 连接账号
		print('创建1实例中...')
		instance_id, public_ip, startup, inner_ip = create_instance(clt, imageid, InstanceType)
		print('创建2实例中...')
		instance_id2, public_ip2, startup2, inner_ip2 = create_instance(clt, imageid, InstanceType)
		print('进行评测')
		sysbench_result, netperf_result = run(public_ip1, public_ip2, inner_ip2, threads_num)
		get_json(sysbench_result, netperf_result)
		destrop_instance(clt, instance_id)
		destrop_instance(clt, instance_id2)


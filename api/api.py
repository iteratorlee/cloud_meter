# -*- coding=utf-8 -*-

from flask import Flask, request, jsonify
import json
import logging
import time
from aliyunsdkcore import client
from aliyunsdkecs.request.v20140526.DescribePriceRequest import DescribePriceRequest
from aliyunsdkecs.request.v20140526.CreateInstanceRequest import CreateInstanceRequest
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
from aliyunsdkecs.request.v20140526.StartInstanceRequest import StartInstanceRequest
from aliyunsdkecs.request.v20140526.AllocatePublicIpAddressRequest import AllocatePublicIpAddressRequest
from aliyunsdkecs.request.v20140526.DeleteInstanceRequest import DeleteInstanceRequest
from aliyunsdkecs.request.v20140526.StopInstanceRequest import StopInstanceRequest
from ucloud.core import exc
from ucloud.client import Client

# 阿里云的账户信息
AccessKeyId = ""
AccessKeySecret = ""
# UCloud的账户信息
PublicKey = ""
PrivateKey = ""

app = Flask(__name__)

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

# 创建主机并分配公网ip
@app.route('/CreateInstanceGetIp')
def create_instance_get_ip():
	# 获取需要的参数
	vendor = request.args.get("vendor")
	InstanceType = request.args.get("instancetype")
	imageid = request.args.get("imageid")
	regionid = request.args.get("regionid")

	# 阿里云
	if vendor == 'aliyun':
		# 测试：http://123.56.57.3:5000/CreateInstanceGetIp?vendor=aliyun&instancetype=ecs.g6.large&regionid=cn-beijing&imageid=ubuntu_18_04_64_20G_alibase_20190624.vhd
		try:
			global client
			clt = client.AcsClient(AccessKeyId, AccessKeySecret, regionid)	# 连接账号
			Request = CreateInstanceRequest()								# 创建主机
			InternetChargeType = 'PayByTraffic'								# 网络付费模式
			InternetMaxBandwidthOut = '5'									# 带宽
			Request.set_ImageId(imageid)
			Request.set_InstanceType(InstanceType)
			Request.set_InternetChargeType(InternetChargeType)
			Request.set_InternetMaxBandwidthOut(InternetMaxBandwidthOut)
			Response = clt.do_action_with_exception(Request)
			Response = json.loads(str(Response, encoding = 'utf8'))			# 正确返回
			instance_id = Response.get('InstanceId')
			
			# 阿里云需要主机初始化完成之后才能分配公网ip，即需要主机状态为Stopped，再分配ip，否则报错
			detail = get_instance_detail_by_id(clt, instance_id)
			index = 0
			while detail is None and index < 60:
				detail = get_instance_detail_by_id(clt, instance_id)
				time.sleep(1)
			
			# 分配公网ip
			Request = AllocatePublicIpAddressRequest()
			Request.set_InstanceId(instance_id)
			Response = clt.do_action_with_exception(Request)
			Response = json.loads(str(Response, encoding = 'utf8'))
			if Response is not None:
				publicip = Response.get('IpAddress')
			
			# 启动主机
			Request = StartInstanceRequest()
			Request.set_InstanceId(instance_id)
			clt.do_action_with_exception(Request)
		except Exception as e:
			exceptstr = str(e).replace('Error:', '*').replace('HTTP Status:', '*').replace('RequestID:', '*').split('*')
			ret = {}
			ret['HTTP Status'] = exceptstr[1].strip()
			ret['Error'] = exceptstr[2].strip()
			return jsonify(ret)
		else:
			# 正确情况返回json，包含instance_id和公网ip
			ret = {}
			ret['InstanceId'] = instance_id
			ret['PublicIp'] = publicip
			return jsonify(ret)

	# UCloud
	elif vendor == 'ucloud':
		# 测试：http://123.56.57.3:5000/CreateInstanceGetIp?vendor=ucloud&instancetype=n.2.4&regionid=cn-bj2&imageid=uimage-irofn4&zoneid=cn-bj2-05
		try:
			zoneid = request.args.get('zoneid')
			clt = Client({"region": regionid, "public_key": PublicKey, "private_key": PrivateKey})
			MachineType = InstanceType.split('.')[0].upper()
			CPU = int(InstanceType.split('.')[1])
			Memory = int(InstanceType.split('.')[2]) * 1024
			resp = clt.uhost().create_uhost_instance({
				'Zone': zoneid,
				'MachineType': MachineType,
                'CPU': CPU,
                'Memory': Memory,
                'LoginMode': 'Password',
                'Password': 'jd123456',
				'ChargeType': 'Dynamic',
				'Disks.0.Size': 40,
                'Disks.0.IsBoot': 'True',
                'Disks.0.Type': 'CLOUD_SSD',
                'ImageId': imageid,
				'NetworkInterface.0.EIP.Bandwidth': 5,
				'NetworkInterface.0.EIP.PayMode': 'Traffic',
				'NetworkInterface.0.EIP.OperatorName': 'Bgp'
            })
			instance_id = resp.get('UHostIds')[0]
			resp = clt.unet().allocate_eip({
				'OperatorName': 'Bgp',	
				'Bandwidth': 5,
				'PayMode': 'Traffic',
			})
			public_ip = resp.get('EIPSet')[0].get('EIPAddr')[0].get('IP')
			public_ipid = resp.get('EIPSet')[0].get('EIPId')
			resp = clt.unet().bind_eip({
                'EIPId': public_ipid,  
                'ResourceType': 'uhost',
                'ResourceId': instance_id,
            })
		except exc.ValidationException as e:
			return '参数校验错误' + str(e)
		except exc.RetCodeException as e:
			return '后端返回 RetCode 不为 0 错误' + str(e)
		except exc.UCloudException as e:
			return 'SDK 其它错误' + str(e)
		except Exception as e:
			return '其它错误' + str(e)
		else:
			ret = {}
			ret['InstanceId'] = instance_id
			ret['PublicIp'] = public_ip
			return jsonify(ret)
	
	else:
		ret = {}
		ret['HTTP Status'] = '404'
		ret['Error'] = 'Wrong Vendor'
		return jsonify(ret)

# 销毁主机
@app.route('/DestroyInstance')
def destroy_instance():
	vendor = request.args.get("vendor")
	regionid = request.args.get("regionid")
	instanceid = request.args.get("instanceid")
	
	if vendor == 'aliyun':
		try:
			global client
			clt = client.AcsClient(AccessKeyId, AccessKeySecret, regionid)						
			Request = DeleteInstanceRequest()
			Request.set_InstanceId(instanceid)
			Request.set_Force(True)
			clt.do_action_with_exception(Request)
		except Exception as e:
			exceptstr = str(e).replace('Error:', '*').replace('HTTP Status:', '*').replace('RequestID:', '*').split('*')
			ret = {}
			ret['HTTP Status'] = exceptstr[1].strip()
			ret['Error'] = exceptstr[2].strip()
			return jsonify(ret)
		else:
			return 'The instance is successfully destroyed.'
	
	elif vendor == 'ucloud':
		try:
			clt = Client({"region": regionid, "public_key": PublicKey, "private_key": PrivateKey})
			resp = clt.uhost().stop_uhost_instance({
				'UHostId': instanceid
            })
			resp = clt.uhost().terminate_uhost_instance({
				'UHostId': instanceid,
				'ReleaseEIP': True,
				'ReleaseUDisk': True
            })
		except exc.ValidationException as e:
			return '参数校验错误' + str(e)
		except exc.RetCodeException as e:
			return '后端返回 RetCode 不为 0 错误' + str(e)
		except exc.UCloudException as e:
			return 'SDK 其它错误' + str(e)
		except Exception as e:
			return '其它错误' + str(e)
		else:
			return 'The instance is successfully destroyed.'

	else:
		ret = {}
		ret['HTTP Status'] = '404'
		ret['Error'] = 'Wrong Vendor'
		return jsonify(ret)


@app.route('/GetPrices')
def get_prices():
	vendor = request.args.get("vendor")
	InstanceType = request.args.get("instancetype")
	regionid = request.args.get("regionid")
	
	result = {}
	if vendor == 'aliyun':
		try:
			clt = client.AcsClient(AccessKeyId, AccessKeySecret, regionid)
			Request = DescribePriceRequest()
			Request.set_InstanceType(InstanceType)
			Response = clt.do_action_with_exception(Request)
			Response = json.loads(str(Response, encoding = 'utf8'))	
			result[InstanceType] = Response["PriceInfo"]["Price"]["TradePrice"]
		except Exception as e:
			exceptstr = str(e).replace('Error:', '*').replace('HTTP Status:', '*').replace('RequestID:', '*').split('*')
			ret = {}
			ret['HTTP Status'] = exceptstr[1].strip()
			ret['Error'] = exceptstr[2].strip()
			return jsonify(ret)
		else:
			return jsonify(result)

	elif vendor == 'ucloud':
		try:
			clt = Client({"region": regionid, "public_key": PublicKey, "private_key": PrivateKey})
			MachineType = InstanceType.split('.')[0].upper()
			CPU = int(InstanceType.split('.')[1])
			Memory = int(InstanceType.split('.')[2]) * 1024
			resp = clt.uhost().get_uhost_instance_price({
				'MachineType': MachineType,
				'CPU': CPU,
				'Memory': Memory,
				'Count': 1,
				'ChargeType': 'Dynamic',
				'Disks.0.Size': 40,
				'Disks.0.IsBoot': 'True',
				'Disks.0.Type': 'CLOUD_SSD',
				'ImageId': 'uimage-irofn4'
			})
		except exc.ValidationException as e:
			return '参数校验错误' + str(e)
		except exc.RetCodeException as e:
			return '后端返回 RetCode 不为 0 错误' + str(e)
		except exc.UCloudException as e:
			return 'SDK 其它错误' + str(e)
		except Exception as e:
			return '其它错误' + str(e)
		else:
			result[InstanceType] = resp["PriceSet"][0]["Price"]
			return jsonify(result)
	
	else:
		ret = {}
		ret['HTTP Status'] = '404'
		ret['Error'] = 'Wrong Vendor'
		return jsonify(ret)


if __name__ == '__main__':
	app.run(host="0.0.0.0", port=5000)

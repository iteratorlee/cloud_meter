# -*- coding = utf-8 -*-
import json
import os

def getMark(ct, mt, it, nt):
	cmark = round(2500 / ct, 1)
	mmark = round(9500 / mt, 1)
	imark = round(8500 / it)
	nmark = round(nt / 250)
	return cmark, mmark, imark, nmark, cmark+mmark+imark+nmark

def main():
	instanceIds = ["通用型ecs.g6.large", "计算型ecs.c6.xlarge", "内存型ecs.r6.large", "标准型",
		"计算型", "内存型", "通用型2核8G", "通用型4核8G", "通用型2核16G"]
	regions = {'cn-beijing': '北京', 'cn-hongkong': '香港', 'cn-shanghai': '上海', 'cn-shenzhen': '深圳',
		'ap-beijing': '北京', 'ap-guangzhou': '广州', 'ap-shanghai': '上海',
		'cn-bj2': '北京', 'cn-gd': '广东', 'cn-sh2': '上海', 'hk': '香港'}
	configs = ["2vCPU / 8GB", "4vCPU / 8GB", "2vCPU / 16GB"]
	factorys = ['阿里云', '腾讯云', 'uCloud']
	markdatas = [0] * 9
	markjson = {}
	path = 'bench_result_1216'
	date = '2019/12/16'
	files = os.listdir(path)
	for file in files:
		if file[:5] != 'bench':
			continue
		file_path = path + '/' + file
		instanceId = file.split('_')[4]
		region = regions[file.split('_')[3]]
		if instanceId[0] == 'S':
			instanceIds[3] = instanceIds[3] + instanceId
		if instanceId[0] == 'C':
			instanceIds[4] = instanceIds[4] + instanceId
		if instanceId[0] == 'M':
			instanceIds[5] = instanceIds[5] + instanceId
		if instanceId[0] == 'N':
			filesplit = instanceId.split('-')
			instanceId = filesplit[1] + '核' + str(int(int(filesplit[2])/1024)) + 'G'
		tmpbench = {}; index = -1
		for i in range(len(instanceIds)):
			if instanceIds[i].find(instanceId) > 0:
				tmpbench['instanceId'] = instanceIds[i]
				tmpbench['config'] = configs[i%3]
				tmpbench['factory'] = factorys[int(i/3)]
				tmpbench['region'] = region
				index = i
				break
		benchresult = {}	
		with open(file_path, 'r') as fi:
			benchresult = json.load(fi)
		cputime = 0; memtime = 0; iotime = 0; nettime = 0
		for item in benchresult['cpu']:
			cputime = cputime + float(item['total_time'][:-1])
		for item in benchresult['mem']:
			memtime = memtime + float(item['total_time'][:-1])
		for item in benchresult['io']:
			iotime = iotime + float(item['total_time'][:-1])
		for k in benchresult['net']:
			nettime = nettime + benchresult['net'][k]
		tmpbench['open'] = str(round(benchresult['startup_time'], 1)) + 's'
		tmpbench['cpu'], tmpbench['memory'], tmpbench['io'], tmpbench['network'], tmpbench['total']\
			= getMark(cputime, memtime, iotime, nettime)
		markdatas[index] = tmpbench
	markjson['date'] = date
	markjson['datas'] = markdatas
	with open('html/json/meters.json', 'r') as fmeters:
		meters = json.load(fmeters)
	meters.insert(0, markjson)
	print(len(meters))
	with open('html/json/meters.json', 'w') as f:
		json.dump(meters, f, ensure_ascii=False)

if __name__ == '__main__':
	main()
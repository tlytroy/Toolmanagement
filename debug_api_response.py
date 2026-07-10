#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def debug_api_response():
    """
    调试API响应，查看详细信息
    """
    print("调试API响应...")
    
    # 读取测试图像
    with open('test_results/original/testpic.jpg', 'rb') as f:
        image_data = f.read()
    
    # 发送到后端API
    files = {'file': ('testpic.jpg', image_data, 'image/jpeg')}
    
    try:
        response = requests.post('http://localhost:8000/process-image', files=files)
        
        if response.status_code == 200:
            result = response.json()
            
            if result['success']:
                print("✓ 后端处理成功!")
                print(f"检测到的基元数量: {len(result['primitives'])}")
                
                # 显示基元统计
                summary = result['summary']
                print(f"基元统计: {summary}")
                
                # 显示检测到的角点
                corners = result['calibration']['corners']
                print("检测到的纸张四角:")
                corner_names = ['左上', '右上', '右下', '左下']
                for i, corner in enumerate(corners):
                    print(f"  {corner_names[i]}: ({corner['x']:.1f}, {corner['y']:.1f})")
                
                # 显示前10个基元详情
                print("\n前10个基元详情:")
                for i, primitive in enumerate(result['primitives'][:10]):
                    if primitive['type'] == 'line':
                        p0 = primitive['p0']
                        p1 = primitive['p1']
                        print(f"  直线 {i+1}: ({p0['x']:.1f}, {p0['y']:.1f}) → ({p1['x']:.1f}, {p1['y']:.1f})")
                    elif primitive['type'] == 'arc':
                        center = primitive['center']
                        radius = primitive['radius']
                        print(f"  圆弧 {i+1}: 中心({center['x']:.1f}, {center['y']:.1f}), 半径{radius:.1f}")
                    elif primitive['type'] == 'polyline':
                        points = primitive['points']
                        print(f"  折线 {i+1}: {len(points)}个点")
                        
                # 检查是否有圆弧
                arcs = [p for p in result['primitives'] if p['type'] == 'arc']
                if arcs:
                    print(f"\n发现 {len(arcs)} 个圆弧基元!")
                else:
                    print(f"\n注意: 没有检测到圆弧基元，全是直线段")
                
            else:
                print(f"✗ 后端处理失败: {result.get('error', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务，请确保后端服务正在运行")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

if __name__ == "__main__":
    debug_api_response()
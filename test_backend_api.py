#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试后端API的纸张检测功能
"""

import requests
import cv2
import json

def test_paper_detection():
    """测试纸张检测API"""
    print("🔍 测试后端API纸张检测功能...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    
    try:
        # 发送POST请求到后端API
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('http://localhost:8001/process-image', files=files)
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API响应成功!")
            print(f"   处理状态: {'成功' if result['success'] else '失败'}")
            
            if result['success']:
                corners = result['calibration']['corners']
                print(f"   检测到纸张角点: {corners}")
                print(f"   轮廓基元数量: {len(result['primitives'])}")
                
                # 验证角点格式
                if len(corners) == 4:
                    print("✅ 纸张检测功能正常!")
                    return True
                else:
                    print("❌ 角点数量不正确")
                    return False
            else:
                print(f"❌ 处理失败: {result.get('error', '未知错误')}")
                return False
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return False
            
    except FileNotFoundError:
        print(f"❌ 找不到测试图像: {image_path}")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务，请确保服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    success = test_paper_detection()
    if success:
        print("\n🎉 后端纸张检测功能测试通过!")
    else:
        print("\n💥 后端纸张检测功能测试失败!")
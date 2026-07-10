import requests

# 测试图像处理功能
def test_image_processing():
    try:
        # 使用项目中的测试图片
        with open('testpic.jpg', 'rb') as f:
            files = {'file': ('testpic.jpg', f, 'image/jpeg')}
            response = requests.post('http://localhost:8000/process-image', files=files)
            
        print(f"图像处理响应状态: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"处理结果: {result}")
            
            if result.get('success'):
                print("\n✅ 图像处理成功!")
                print(f"检测到的基元数量: {len(result.get('primitives', []))}")
                if result.get('summary'):
                    print(f"基元统计: {result['summary']}")
                print("校正后的图像已生成")
            else:
                print(f"\n❌ 处理失败: {result.get('error', '未知错误')}")
        else:
            print(f"\n❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except FileNotFoundError:
        print("找不到测试图片 testpic.jpg，请确保文件存在")
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    print("开始测试图像处理功能...")
    test_image_processing()
import requests

# 测试后端API是否正常工作
try:
    # 测试根路径
    response = requests.get('http://localhost:8000/')
    print(f"API根路径响应: {response.status_code}")
    print(f"响应内容: {response.json()}")
    
    print("\n后端API测试完成！")
    print("请上传一张测试图片来验证完整的图像处理功能。")
    
except Exception as e:
    print(f"测试失败: {e}")
    print("请确保Python后端服务正在运行 (python_backend/main.py)")
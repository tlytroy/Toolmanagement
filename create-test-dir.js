// 创建测试目录
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const testDir = path.join(__dirname, '__tests__');
if (!fs.existsSync(testDir)) {
  fs.mkdirSync(testDir);
}
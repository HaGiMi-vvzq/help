"""Create test users for matching accuracy testing. Run from backend dir."""
import asyncio
from app.core.security import hash_password
from app.core.database import async_session
from app.models.user import User
from sqlalchemy import select

TEST_USERS = [
    {"username": "前端小王", "password": "123456", "school": "西南科技大学",
     "bio": "熟练 Vue3、React、TypeScript、Tailwind CSS，做过 3 个校园小程序前端。找后端或设计队友做黑客松项目。",
     "skill_tags": ["Vue3", "React", "TypeScript", "Tailwind", "前端开发"]},
    {"username": "后端老李", "password": "123456", "school": "西南科技大学",
     "bio": "Python FastAPI 和 Go 后端开发，熟悉 PostgreSQL、Redis、Docker。帮多个团队搭过项目后端。",
     "skill_tags": ["Python", "FastAPI", "Go", "PostgreSQL", "Redis", "Docker"]},
    {"username": "算法阿强", "password": "123456", "school": "西南科技大学",
     "bio": "ACM 银牌，蓝桥杯国一，日常刷 LeetCode 和 Codeforces。擅长 C++ 算法和数据结构。",
     "skill_tags": ["C++", "算法", "ACM", "蓝桥杯", "数据结构", "LeetCode"]},
    {"username": "数据小张", "password": "123456", "school": "绵阳师范学院",
     "bio": "Python 数据分析方向，会 Pandas、Matplotlib、SQL。参加过数学建模国赛。也懂一点机器学习。",
     "skill_tags": ["Python", "数据分析", "Pandas", "SQL", "数学建模", "机器学习"]},
    {"username": "设计小林", "password": "123456", "school": "绵阳师范学院",
     "bio": "UI/UX 设计，熟练 Figma、PS、AI。做过 5 个校园活动的海报和宣传物料。想找开发队友一起做产品。",
     "skill_tags": ["UI设计", "Figma", "PS", "AI", "平面设计", "产品设计"]},
    {"username": "全栈小陈", "password": "123456", "school": "西南科技大学",
     "bio": "全栈开发，前端 Vue3 后端 FastAPI，数据库 PostgreSQL。独立完成过一个校园二手交易平台。想找队友做大创项目。",
     "skill_tags": ["Vue3", "FastAPI", "PostgreSQL", "全栈", "JavaScript", "Python"]},
    {"username": "Android老周", "password": "123456", "school": "西南科技大学",
     "bio": "Android 原生开发 3 年，Kotlin + Jetpack Compose。也懂 Flutter 跨平台。有上架应用宝的经验。",
     "skill_tags": ["Android", "Kotlin", "Flutter", "Java", "移动开发", "Jetpack"]},
    {"username": "NLP小赵", "password": "123456", "school": "西南科技大学",
     "bio": "NLP 方向研究生，做文本分类和情感分析。熟练 PyTorch、Transformers、RAG。想找工程能力强的队友把模型落地。",
     "skill_tags": ["PyTorch", "NLP", "Transformers", "RAG", "Python", "机器学习"]},
    {"username": "产品小周", "password": "123456", "school": "绵阳师范学院",
     "bio": "产品经理方向，做过 2 个校园产品的需求分析和原型设计。熟练 Axure、墨刀。擅长商业计划书和路演。",
     "skill_tags": ["产品设计", "Axure", "需求分析", "商业计划书", "路演", "项目管理"]},
    {"username": "网安小吴", "password": "123456", "school": "西南科技大学",
     "bio": "网络安全方向，参加过 CTF 比赛，熟悉 Web 安全和渗透测试。也在学 AI 安全方向。",
     "skill_tags": ["网络安全", "CTF", "Web安全", "渗透测试", "Python", "Linux"]},
    {"username": "嵌入式大刘", "password": "123456", "school": "西南科技大学",
     "bio": "嵌入式开发，熟练 STM32、ESP32、Arduino。做过智能家居和无人机飞控项目。会 C 和 Python。",
     "skill_tags": ["嵌入式", "STM32", "ESP32", "C语言", "Python", "IoT"]},
    {"username": "测试小黄", "password": "123456", "school": "绵阳师范学院",
     "bio": "软件测试方向，会自动化测试 Selenium 和接口测试 Postman。写过测试用例文档。想找开发团队实习。",
     "skill_tags": ["软件测试", "Selenium", "Postman", "自动化测试", "Python"]},
    {"username": "视频小郑", "password": "123456", "school": "绵阳师范学院",
     "bio": "视频剪辑和后期制作，熟练 PR、AE、达芬奇。帮学校剪过招生宣传片。想找需要视频能力的团队。",
     "skill_tags": ["视频剪辑", "PR", "AE", "达芬奇", "后期制作"]},
    {"username": "英语小孙", "password": "123456", "school": "绵阳师范学院",
     "bio": "英语专业，TEM-8，做过论文翻译和口译。想用英语能力换编程教学，尤其是 Python 入门。",
     "skill_tags": ["英语", "翻译", "口译", "Python入门"]},
    {"username": "区块链小胡", "password": "123456", "school": "西南科技大学",
     "bio": "区块链开发，Solidity 智能合约 + Web3.js。做过 NFT 交易市场 demo。找前端和后端一起做 DApp。",
     "skill_tags": ["区块链", "Solidity", "Web3", "智能合约", "JavaScript", "Go"]},
]


async def create_users():
    async with async_session() as db:
        created = skipped = 0
        for data in TEST_USERS:
            result = await db.execute(select(User).where(User.username == data["username"]))
            if result.scalar_one_or_none():
                skipped += 1
                continue
            user = User(
                username=data["username"],
                password_hash=hash_password(data["password"]),
                school=data["school"],
                bio=data["bio"],
                skill_tags=data["skill_tags"],
            )
            db.add(user)
            created += 1
            print(f"  Created: {data['username']} ({', '.join(data['skill_tags'][:3])}...)")
        await db.commit()
    print(f"\nDone: {created} created, {skipped} already existed")


if __name__ == "__main__":
    asyncio.run(create_users())

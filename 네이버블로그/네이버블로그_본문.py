import asyncio
from playwright.async_api import async_playwright

async def get_blog_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        
        # iframe 진입
        frame = page.frame(name="mainFrame")
        if frame:
            await frame.wait_for_selector(".se-main-container", timeout=5000)
            content = await frame.inner_text(".se-main-container")
        else:
            content = "본문을 찾을 수 없음"
        
        await browser.close()
        return content

content = asyncio.run(get_blog_content("https://blog.naver.com/sil6032/224327204683"))
print(content)
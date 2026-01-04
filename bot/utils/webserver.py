#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: webserver.py
Author: Maria Kevin
Created: 2025-12-23
Description: Simple aiohttp web server with self-ping functionality
"""

import asyncio
import logging
import os

from aiohttp import ClientSession, web

__author__ = "Maria Kevin"
__version__ = "0.1.0"

logger = logging.getLogger(__name__)


async def start_webserver():
    """Start a simple aiohttp web server in the background"""
    routes = web.RouteTableDef()

    @routes.get("/", allow_head=True)
    async def root_route_handler(request):
        """Health check endpoint"""
        return web.json_response({
            "status": "running",
            "message": "Bot is alive!"
        })

    async def web_server():
        """Create and configure the web application"""
        web_app = web.Application(client_max_size=30000000)
        web_app.add_routes(routes)
        return web_app

    # Start the web server
    app = web.AppRunner(await web_server())
    await app.setup()
    
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8000))
    try:
        await web.TCPSite(app, "0.0.0.0", port).start()
    except:
        pass
    
    logger.info(f"Web server started on port {port}")
    
    # Start the ping task in the background
    asyncio.create_task(ping_server())


async def ping_server():
    """Ping the WEB_URL every 2-3 minutes to keep the server alive"""
    web_url = os.environ.get("WEB_URL")
    
    if not web_url:
        logger.warning("WEB_URL not set in environment variables. Ping functionality disabled.")
        return
    
    logger.info(f"Starting ping task for {web_url}")
    
    # Random interval between 2-3 minutes (120-180 seconds)
    import random
    
    async with ClientSession() as session:
        while True:
            try:
                # Wait 2-3 minutes before pinging
                wait_time = random.randint(120, 180)
                await asyncio.sleep(wait_time)
                
                # Ping the server
                async with session.get(web_url) as response:
                    if response.status == 200:
                        logger.debug(f"✅ Ping successful: {web_url} (Status: {response.status})")
                    else:
                        logger.warning(f"⚠️ Ping returned status {response.status}: {web_url}")
                        
            except Exception as e:
                logger.error(f"❌ Ping failed for {web_url}: {e}")
                # Continue the loop even if ping fails
                await asyncio.sleep(120)  # Wait 2 minutes before retrying

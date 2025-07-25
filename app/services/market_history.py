"""
Market history service for persistent time series storage
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

class MarketHistoryService:
    """Service for managing market history data in PostgreSQL"""
    
    @staticmethod
    async def store_price_point(
        db: AsyncSession,
        region: str,
        realm: str,
        item_id: int,
        price: float,
        quantity: int
    ) -> bool:
        """Store a single price data point"""
        try:
            await db.execute(text("""
                INSERT INTO market_history (id, region, realm_slug, item_id, price, quantity, timestamp)
                VALUES (:id, :region, :realm, :item_id, :price, :quantity, :timestamp)
            """), {
                "id": str(uuid.uuid4()),
                "region": region,
                "realm": realm,
                "item_id": item_id,
                "price": price,
                "quantity": quantity,
                "timestamp": datetime.utcnow()
            })
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing price point: {e}")
            await db.rollback()
            return False
    
    @staticmethod
    async def bulk_store_price_points(
        db: AsyncSession,
        price_points: List[Dict[str, Any]]
    ) -> int:
        """Store multiple price points efficiently"""
        try:
            if not price_points:
                return 0
                
            # Prepare data for bulk insert
            timestamp = datetime.utcnow()
            insert_data = []
            
            for point in price_points:
                insert_data.append({
                    "id": str(uuid.uuid4()),
                    "region": point["region"],
                    "realm": point["realm"],
                    "item_id": point["item_id"],
                    "price": point["price"],
                    "quantity": point["quantity"],
                    "timestamp": timestamp
                })
            
            # Bulk insert
            await db.execute(text("""
                INSERT INTO market_history (id, region, realm_slug, item_id, price, quantity, timestamp)
                VALUES (:id, :region, :realm, :item_id, :price, :quantity, :timestamp)
            """), insert_data)
            
            await db.commit()
            return len(insert_data)
            
        except Exception as e:
            logger.error(f"Error bulk storing price points: {e}")
            await db.rollback()
            return 0
    
    @staticmethod
    async def get_price_trends(
        db: AsyncSession,
        region: str,
        realm: str,
        item_id: int,
        hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Get price trends for an item"""
        try:
            result = await db.execute(text("""
                SELECT * FROM get_price_trends(:region, :realm, :item_id, :hours)
            """), {
                "region": region,
                "realm": realm,
                "item_id": item_id,
                "hours": hours
            })
            
            row = result.fetchone()
            if row:
                return {
                    "avg_price": float(row.avg_price) if row.avg_price else 0,
                    "min_price": float(row.min_price) if row.min_price else 0,
                    "max_price": float(row.max_price) if row.max_price else 0,
                    "price_volatility": float(row.price_volatility) if row.price_volatility else 0,
                    "data_points": row.data_points,
                    "oldest_timestamp": row.oldest_timestamp,
                    "newest_timestamp": row.newest_timestamp
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting price trends: {e}")
            return None
    
    @staticmethod
    async def get_historical_data_points(
        db: AsyncSession,
        region: str,
        realm: str,
        item_id: int,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get raw historical data points"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            result = await db.execute(text("""
                SELECT price, quantity, timestamp
                FROM market_history
                WHERE region = :region
                    AND realm_slug = :realm
                    AND item_id = :item_id
                    AND timestamp > :cutoff
                ORDER BY timestamp DESC
            """), {
                "region": region,
                "realm": realm,
                "item_id": item_id,
                "cutoff": cutoff_time
            })
            
            return [
                {
                    "price": float(row.price),
                    "quantity": row.quantity,
                    "timestamp": row.timestamp.isoformat()
                }
                for row in result.fetchall()
            ]
            
        except Exception as e:
            logger.error(f"Error getting historical data points: {e}")
            return []
    
    @staticmethod
    async def record_snapshot(
        db: AsyncSession,
        realms_updated: int,
        items_tracked: int,
        execution_time: float,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> bool:
        """Record a market update snapshot"""
        try:
            await db.execute(text("""
                INSERT INTO market_snapshots (
                    id, snapshot_time, realms_updated, items_tracked, 
                    success, error_message, execution_time_seconds
                )
                VALUES (
                    :id, :snapshot_time, :realms_updated, :items_tracked,
                    :success, :error_message, :execution_time
                )
            """), {
                "id": str(uuid.uuid4()),
                "snapshot_time": datetime.utcnow(),
                "realms_updated": realms_updated,
                "items_tracked": items_tracked,
                "success": success,
                "error_message": error_message,
                "execution_time": execution_time
            })
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error recording snapshot: {e}")
            await db.rollback()
            return False
    
    @staticmethod
    async def get_snapshot_history(
        db: AsyncSession,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent snapshot history"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            result = await db.execute(text("""
                SELECT snapshot_time, realms_updated, items_tracked, 
                       success, execution_time_seconds
                FROM market_snapshots
                WHERE snapshot_time > :cutoff
                ORDER BY snapshot_time DESC
            """), {
                "cutoff": cutoff_time
            })
            
            return [
                {
                    "snapshot_time": row.snapshot_time.isoformat(),
                    "realms_updated": row.realms_updated,
                    "items_tracked": row.items_tracked,
                    "success": row.success,
                    "execution_time": float(row.execution_time_seconds) if row.execution_time_seconds else 0
                }
                for row in result.fetchall()
            ]
            
        except Exception as e:
            logger.error(f"Error getting snapshot history: {e}")
            return []
    
    @staticmethod
    async def cleanup_old_data(db: AsyncSession) -> int:
        """Clean up data older than 7 days"""
        try:
            result = await db.execute(text("SELECT cleanup_old_market_data()"))
            rows_deleted = result.scalar()
            await db.commit()
            logger.info(f"Cleaned up {rows_deleted} old market history records")
            return rows_deleted
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            await db.rollback()
            return 0
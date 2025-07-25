"""
Auction data aggregator service for comprehensive market analysis
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import logging

logger = logging.getLogger(__name__)

class AuctionAggregatorService:
    """Service for aggregating auction data into meaningful market metrics"""
    
    @staticmethod
    def aggregate_auction_data(auctions: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """
        Aggregate raw auction data by item ID
        
        Returns dict of item_id -> aggregated metrics
        """
        item_aggregates = defaultdict(lambda: {
            'prices': [],
            'quantities': [],
            'sellers': set(),
            'auctions': [],
            'price_points': defaultdict(lambda: {'quantity': 0, 'count': 0, 'sellers': set()})
        })
        
        for auction in auctions:
            item_id = auction.get('item', {}).get('id', 0)
            if not item_id:
                continue
                
            quantity = auction.get('quantity', 1)
            buyout = auction.get('buyout', 0)
            
            if buyout > 0 and quantity > 0:
                price_per_unit = buyout / quantity
                seller_id = auction.get('seller', {}).get('id', 'unknown')
                
                agg = item_aggregates[item_id]
                agg['prices'].extend([price_per_unit] * quantity)  # Weight by quantity
                agg['quantities'].append(quantity)
                agg['sellers'].add(seller_id)
                agg['auctions'].append(auction)
                
                # Track price distribution
                price_bucket = round(price_per_unit, 2)  # Round to copper
                agg['price_points'][price_bucket]['quantity'] += quantity
                agg['price_points'][price_bucket]['count'] += 1
                agg['price_points'][price_bucket]['sellers'].add(seller_id)
        
        # Calculate final metrics
        results = {}
        for item_id, data in item_aggregates.items():
            if not data['prices']:
                continue
                
            prices = np.array(data['prices'])
            quantities = np.array(data['quantities'])
            
            # Calculate seller concentration
            seller_quantities = defaultdict(int)
            for auction in data['auctions']:
                seller_id = auction.get('seller', {}).get('id', 'unknown')
                seller_quantities[seller_id] += auction.get('quantity', 1)
            
            total_quantity = sum(quantities)
            top_seller_qty = max(seller_quantities.values()) if seller_quantities else 0
            
            results[item_id] = {
                'total_quantity': int(total_quantity),
                'auction_count': len(data['auctions']),
                'unique_sellers': len(data['sellers']),
                'min_price': float(np.min(prices)),
                'max_price': float(np.max(prices)),
                'avg_price': float(np.mean(prices)),
                'median_price': float(np.median(prices)),
                'std_dev_price': float(np.std(prices)) if len(prices) > 1 else 0,
                'top_seller_quantity': int(top_seller_qty),
                'top_seller_percentage': float(top_seller_qty / total_quantity * 100) if total_quantity > 0 else 0,
                'total_market_value': float(sum(quantities * prices[:len(quantities)])),
                'price_distribution': data['price_points']
            }
        
        return results
    
    @staticmethod
    async def store_market_snapshot(
        db: AsyncSession,
        region: str,
        realm_slug: str,
        connected_realm_id: str,
        aggregated_data: Dict[int, Dict[str, Any]]
    ) -> int:
        """Store aggregated market snapshot data"""
        try:
            timestamp = datetime.utcnow()
            snapshots_stored = 0
            
            for item_id, metrics in aggregated_data.items():
                snapshot_id = str(uuid.uuid4())
                
                # Store main snapshot
                await db.execute(text("""
                    INSERT INTO auction_market_snapshots (
                        id, timestamp, region, realm_slug, connected_realm_id, item_id,
                        total_quantity, auction_count, unique_sellers,
                        min_price, max_price, avg_price, median_price, std_dev_price,
                        top_seller_quantity, top_seller_percentage, total_market_value
                    ) VALUES (
                        :id, :timestamp, :region, :realm_slug, :connected_realm_id, :item_id,
                        :total_quantity, :auction_count, :unique_sellers,
                        :min_price, :max_price, :avg_price, :median_price, :std_dev_price,
                        :top_seller_quantity, :top_seller_percentage, :total_market_value
                    )
                """), {
                    'id': snapshot_id,
                    'timestamp': timestamp,
                    'region': region,
                    'realm_slug': realm_slug,
                    'connected_realm_id': connected_realm_id,
                    'item_id': item_id,
                    **{k: v for k, v in metrics.items() if k != 'price_distribution'}
                })
                
                # Store price distribution details
                price_dist_data = []
                total_qty = metrics['total_quantity']
                
                for price_point, dist_data in metrics['price_distribution'].items():
                    price_dist_data.append({
                        'id': str(uuid.uuid4()),
                        'snapshot_id': snapshot_id,
                        'price_point': float(price_point),
                        'quantity_at_price': dist_data['quantity'],
                        'sellers_at_price': len(dist_data['sellers']),
                        'percentage_of_market': float(dist_data['quantity'] / total_qty * 100) if total_qty > 0 else 0
                    })
                
                if price_dist_data:
                    await db.execute(text("""
                        INSERT INTO auction_price_distributions (
                            id, snapshot_id, price_point, quantity_at_price, 
                            sellers_at_price, percentage_of_market
                        ) VALUES (
                            :id, :snapshot_id, :price_point, :quantity_at_price,
                            :sellers_at_price, :percentage_of_market
                        )
                    """), price_dist_data)
                
                snapshots_stored += 1
            
            await db.commit()
            logger.info(f"Stored {snapshots_stored} market snapshots for {realm_slug}-{region}")
            return snapshots_stored
            
        except Exception as e:
            logger.error(f"Error storing market snapshots: {e}")
            await db.rollback()
            return 0
    
    @staticmethod
    async def get_items_by_quantity(
        db: AsyncSession,
        region: str,
        realm_slug: str,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get items ranked by average quantity in market"""
        try:
            result = await db.execute(text("""
                SELECT * FROM get_items_by_quantity(:region, :realm, :hours, :limit)
            """), {
                'region': region,
                'realm': realm_slug,
                'hours': hours,
                'limit': limit
            })
            
            return [
                {
                    'item_id': row.item_id,
                    'avg_quantity': float(row.avg_quantity),
                    'avg_price': float(row.avg_price),
                    'total_auctions': row.total_auctions,
                    'snapshots_count': row.snapshots_count,
                    'quantity_trend': float(row.quantity_trend) if row.quantity_trend else 0
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            logger.error(f"Error getting items by quantity: {e}")
            return []
    
    @staticmethod
    async def get_market_depth(
        db: AsyncSession,
        region: str,
        realm_slug: str,
        item_id: int
    ) -> List[Dict[str, Any]]:
        """Get market depth (all price points) for an item"""
        try:
            result = await db.execute(text("""
                SELECT * FROM get_market_depth(:region, :realm, :item_id)
            """), {
                'region': region,
                'realm': realm_slug,
                'item_id': item_id
            })
            
            return [
                {
                    'price_point': float(row.price_point),
                    'total_quantity': row.total_quantity,
                    'seller_count': row.seller_count,
                    'market_share': float(row.market_share) if row.market_share else 0,
                    'cumulative_quantity': row.cumulative_quantity
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            logger.error(f"Error getting market depth: {e}")
            return []
    
    @staticmethod
    async def calculate_market_velocity(
        db: AsyncSession,
        region: str,
        realm_slug: str,
        item_id: int,
        previous_snapshot: Optional[Dict[str, Any]] = None,
        current_snapshot: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Calculate market velocity metrics between snapshots"""
        if not previous_snapshot or not current_snapshot:
            return None
            
        try:
            # Calculate changes
            quantity_change = current_snapshot['total_quantity'] - previous_snapshot['total_quantity']
            auction_change = current_snapshot['auction_count'] - previous_snapshot['auction_count']
            price_change = current_snapshot['avg_price'] - previous_snapshot['avg_price']
            
            # Estimate sales (auctions that disappeared)
            estimated_sales = max(0, previous_snapshot['auction_count'] - current_snapshot['auction_count'] + 
                                 max(0, auction_change))
            
            velocity_data = {
                'region': region,
                'realm_slug': realm_slug,
                'item_id': item_id,
                'measurement_date': datetime.utcnow().date(),
                'listings_added': max(0, auction_change),
                'listings_removed': max(0, -auction_change),
                'estimated_sales': estimated_sales,
                'quantity_turnover': abs(quantity_change),
                'price_changes': 1 if abs(price_change) > 0.01 else 0,
                'avg_price_start': previous_snapshot['avg_price'],
                'avg_price_end': current_snapshot['avg_price'],
                'price_volatility': abs(price_change / previous_snapshot['avg_price']) if previous_snapshot['avg_price'] > 0 else 0
            }
            
            # Store velocity data
            await db.execute(text("""
                INSERT INTO market_velocity (
                    id, region, realm_slug, item_id, measurement_date,
                    listings_added, listings_removed, estimated_sales, quantity_turnover,
                    price_changes, avg_price_start, avg_price_end, price_volatility
                ) VALUES (
                    :id, :region, :realm_slug, :item_id, :measurement_date,
                    :listings_added, :listings_removed, :estimated_sales, :quantity_turnover,
                    :price_changes, :avg_price_start, :avg_price_end, :price_volatility
                )
                ON CONFLICT (region, realm_slug, item_id, measurement_date) DO UPDATE SET
                    listings_added = market_velocity.listings_added + EXCLUDED.listings_added,
                    listings_removed = market_velocity.listings_removed + EXCLUDED.listings_removed,
                    estimated_sales = market_velocity.estimated_sales + EXCLUDED.estimated_sales,
                    quantity_turnover = market_velocity.quantity_turnover + EXCLUDED.quantity_turnover,
                    price_changes = market_velocity.price_changes + EXCLUDED.price_changes,
                    avg_price_end = EXCLUDED.avg_price_end,
                    price_volatility = EXCLUDED.price_volatility
            """), {
                'id': str(uuid.uuid4()),
                **velocity_data
            })
            
            await db.commit()
            return velocity_data
            
        except Exception as e:
            logger.error(f"Error calculating velocity: {e}")
            await db.rollback()
            return None
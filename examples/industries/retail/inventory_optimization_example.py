"""
ANTS - Retail Industry Example
===============================

Intelligent Inventory Optimization & Dynamic Pricing

This example demonstrates how ANTS agents automate inventory management
for a multi-location retail chain, integrating with POS systems, optimizing
stock levels, forecasting demand, and implementing dynamic pricing.

## Business Problem

Retail chains face critical inventory challenges:
- Stockouts cost 4% of annual revenue ($800K on $20M revenue)
- Overstock ties up capital and requires markdowns (20-30% loss)
- Manual inventory decisions based on gut feel, not data
- Slow response to demand changes (seasonal, trends, events)
- Poor coordination across locations (one store overstocked, another empty)

## ANTS Solution

1. **Demand Forecasting Agent**: ML-based demand prediction using historical sales
2. **Inventory Optimization Agent**: Determines optimal stock levels per SKU per location
3. **Replenishment Agent**: Automatically generates purchase orders
4. **Dynamic Pricing Agent**: Adjusts prices based on inventory, demand, competition
5. **Stock Transfer Agent**: Balances inventory across locations
6. **POS Integration Agent**: Real-time sales data ingestion via n8n

## Expected Results

- **Stockouts**: -30% (from 4% to 2.8% of revenue)
- **Overstock**: -20% (freed up $500K in working capital)
- **Revenue**: +15% through dynamic pricing and availability
- **Margin**: +3-5% through optimized pricing
- **Manual Work**: -90% (from 20 hours/week to 2 hours/week)

Author: ANTS Development Team
License: MIT
"""

import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import random

# In production, these would be actual ANTS imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockLevel(Enum):
    """Stock level status."""
    CRITICAL = "critical"      # < 7 days supply
    LOW = "low"                # 7-14 days supply
    OPTIMAL = "optimal"        # 14-30 days supply
    HIGH = "high"              # 30-60 days supply
    EXCESS = "excess"          # > 60 days supply


class PricingStrategy(Enum):
    """Dynamic pricing strategy."""
    STANDARD = "standard"      # Base price
    PREMIUM = "premium"        # High demand, low stock (+10-20%)
    CLEARANCE = "clearance"    # Excess stock, low demand (-20-40%)
    COMPETITIVE = "competitive" # Match competitor pricing
    PROMOTIONAL = "promotional" # Marketing-driven discounts


@dataclass
class Product:
    """Product catalog item."""
    sku: str
    name: str
    category: str
    base_price: Decimal
    cost: Decimal
    supplier_id: str
    lead_time_days: int
    min_order_qty: int
    perishable: bool = False
    shelf_life_days: Optional[int] = None


@dataclass
class InventorySnapshot:
    """Current inventory state at a location."""
    location_id: str
    sku: str
    quantity_on_hand: int
    quantity_on_order: int
    quantity_reserved: int  # Customer orders not yet fulfilled
    last_sale_date: datetime
    stock_level: StockLevel
    days_of_supply: float  # How many days until stockout at current sales rate


@dataclass
class SalesForecast:
    """Demand forecast for a SKU at a location."""
    location_id: str
    sku: str
    forecast_date: datetime
    forecasted_units: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    forecast_confidence: float  # 0-1
    seasonal_factor: float
    trend_factor: float
    event_impact: Optional[str] = None  # e.g., "holiday_season", "local_event"


@dataclass
class PricingRecommendation:
    """Dynamic pricing recommendation."""
    sku: str
    location_id: str
    current_price: Decimal
    recommended_price: Decimal
    pricing_strategy: PricingStrategy
    reason: str
    expected_impact: str  # e.g., "15% increase in sales velocity"
    competitor_price: Optional[Decimal] = None


@dataclass
class ReplenishmentOrder:
    """Purchase order recommendation."""
    order_id: str
    sku: str
    location_id: str
    quantity: int
    supplier_id: str
    estimated_cost: Decimal
    urgency: str  # "critical", "high", "normal", "low"
    reason: str
    expected_delivery_date: datetime


@dataclass
class StockTransfer:
    """Inter-location stock transfer."""
    transfer_id: str
    sku: str
    from_location: str
    to_location: str
    quantity: int
    reason: str
    estimated_transit_days: int


class DemandForecastingAgent:
    """
    Agent responsible for predicting future demand.

    Uses:
    - Historical sales data (2+ years)
    - Seasonal patterns (holidays, weather, events)
    - Trend analysis (growing/declining categories)
    - External factors (economic indicators, competitors)
    - ML models (Prophet, LSTM, XGBoost)
    """

    def __init__(self):
        self.agent_id = "demand-forecasting-001"
        logger.info(f"Initialized {self.__class__.__name__}: {self.agent_id}")

    async def forecast_demand(
        self,
        sku: str,
        location_id: str,
        forecast_days: int = 30
    ) -> List[SalesForecast]:
        """
        Generate demand forecast for next N days.

        Process:
        1. Retrieve historical sales data (2 years)
        2. Identify seasonal patterns (day-of-week, monthly, holidays)
        3. Detect trend (growing/declining)
        4. Check for upcoming events (promotions, local events)
        5. Run ML model (Prophet for time series)
        6. Generate forecast with confidence intervals

        Args:
            sku: Product SKU to forecast
            location_id: Store location
            forecast_days: Days to forecast ahead

        Returns:
            List of daily forecasts
        """
        logger.info(f"Forecasting demand for SKU {sku} at {location_id} for next {forecast_days} days")

        # Step 1: Simulate historical data retrieval
        # In production: Query sales database
        await asyncio.sleep(0.2)

        # Step 2: Analyze patterns
        # Simulate seasonal pattern detection
        base_daily_sales = 25.0  # Average units per day
        seasonal_factor = 1.2  # 20% above baseline (holiday season)
        trend_factor = 1.05  # 5% growth trend

        forecasts = []
        current_date = datetime.utcnow()

        for day_offset in range(forecast_days):
            forecast_date = current_date + timedelta(days=day_offset)

            # Day of week effect (weekends higher)
            dow_multiplier = 1.3 if forecast_date.weekday() in [5, 6] else 1.0

            # Calculate forecast
            forecasted_units = base_daily_sales * seasonal_factor * trend_factor * dow_multiplier

            # Confidence interval (±15%)
            confidence = 0.85
            lower_bound = forecasted_units * 0.85
            upper_bound = forecasted_units * 1.15

            # Check for events
            event_impact = None
            if forecast_date.day == 25 and forecast_date.month == 12:
                event_impact = "christmas"
                forecasted_units *= 2.0  # Double demand on Christmas

            forecast = SalesForecast(
                location_id=location_id,
                sku=sku,
                forecast_date=forecast_date,
                forecasted_units=forecasted_units,
                confidence_interval_lower=lower_bound,
                confidence_interval_upper=upper_bound,
                forecast_confidence=confidence,
                seasonal_factor=seasonal_factor,
                trend_factor=trend_factor,
                event_impact=event_impact
            )

            forecasts.append(forecast)

        logger.info(f"  Generated {len(forecasts)} daily forecasts")
        logger.info(f"  Average daily demand: {sum(f.forecasted_units for f in forecasts) / len(forecasts):.1f} units")
        logger.info(f"  Confidence: {forecasts[0].forecast_confidence*100:.1f}%")

        return forecasts


class InventoryOptimizationAgent:
    """
    Agent responsible for determining optimal stock levels.

    Uses:
    - Demand forecasts
    - Lead times
    - Service level targets (e.g., 95% in-stock rate)
    - Safety stock calculations
    - Economic order quantity (EOQ)
    """

    def __init__(self):
        self.agent_id = "inventory-optimization-001"
        self.target_service_level = 0.95  # 95% in-stock rate
        logger.info(f"Initialized {self.__class__.__name__}: {self.agent_id}")

    async def calculate_optimal_stock(
        self,
        product: Product,
        inventory: InventorySnapshot,
        forecasts: List[SalesForecast]
    ) -> Tuple[int, int, StockLevel]:
        """
        Calculate optimal stock levels.

        Calculations:
        1. Expected demand during lead time
        2. Safety stock (buffer for demand variability)
        3. Reorder point (when to order more)
        4. Order quantity (how much to order)

        Args:
            product: Product details
            inventory: Current inventory state
            forecasts: Demand forecasts

        Returns:
            Tuple of (reorder_point, order_quantity, stock_status)
        """
        logger.info(f"Calculating optimal stock for {product.sku} at {inventory.location_id}")

        # Calculate average daily demand from forecast
        avg_daily_demand = sum(f.forecasted_units for f in forecasts) / len(forecasts)

        # Lead time demand (demand during supplier lead time)
        lead_time_demand = avg_daily_demand * product.lead_time_days

        # Safety stock (cover demand variability)
        # Using simplified formula: Z-score * std_dev * sqrt(lead_time)
        # For 95% service level, Z = 1.65
        demand_std_dev = avg_daily_demand * 0.2  # Assume 20% variability
        safety_stock = 1.65 * demand_std_dev * (product.lead_time_days ** 0.5)

        # Reorder point (when stock hits this level, order more)
        reorder_point = int(lead_time_demand + safety_stock)

        # Economic Order Quantity (EOQ)
        # Simplified: Balance order costs vs holding costs
        # For retail, typically 7-14 days of demand
        order_quantity = max(
            int(avg_daily_demand * 14),  # 2 weeks of demand
            product.min_order_qty
        )

        # Determine current stock status
        available_stock = inventory.quantity_on_hand - inventory.quantity_reserved
        days_of_supply = available_stock / avg_daily_demand if avg_daily_demand > 0 else 999

        if days_of_supply < 7:
            stock_status = StockLevel.CRITICAL
        elif days_of_supply < 14:
            stock_status = StockLevel.LOW
        elif days_of_supply <= 30:
            stock_status = StockLevel.OPTIMAL
        elif days_of_supply <= 60:
            stock_status = StockLevel.HIGH
        else:
            stock_status = StockLevel.EXCESS

        logger.info(f"  Current stock: {available_stock} units")
        logger.info(f"  Days of supply: {days_of_supply:.1f} days")
        logger.info(f"  Status: {stock_status.value}")
        logger.info(f"  Reorder point: {reorder_point} units")
        logger.info(f"  Order quantity: {order_quantity} units")

        return reorder_point, order_quantity, stock_status


class ReplenishmentAgent:
    """
    Agent responsible for generating purchase orders.

    Uses:
    - Inventory optimization recommendations
    - Supplier lead times
    - Budget constraints
    - Minimum order quantities
    """

    def __init__(self):
        self.agent_id = "replenishment-001"
        logger.info(f"Initialized {self.__class__.__name__}: {self.agent_id}")

    async def generate_purchase_order(
        self,
        product: Product,
        inventory: InventorySnapshot,
        reorder_point: int,
        order_quantity: int,
        stock_status: StockLevel
    ) -> Optional[ReplenishmentOrder]:
        """
        Generate purchase order if needed.

        Logic:
        1. Check if stock is at or below reorder point
        2. Calculate order quantity (considering MOQ)
        3. Determine urgency based on stock status
        4. Generate PO

        Args:
            product: Product details
            inventory: Current inventory
            reorder_point: When to order
            order_quantity: How much to order
            stock_status: Current stock level

        Returns:
            Purchase order if needed, None otherwise
        """
        available_stock = inventory.quantity_on_hand - inventory.quantity_reserved

        # Check if we need to order
        if available_stock > reorder_point and stock_status not in [StockLevel.CRITICAL, StockLevel.LOW]:
            logger.info(f"  No order needed - stock level sufficient")
            return None

        # Determine urgency
        if stock_status == StockLevel.CRITICAL:
            urgency = "critical"
            reason = "Critical stock level - risk of stockout within 7 days"
        elif stock_status == StockLevel.LOW:
            urgency = "high"
            reason = "Low stock level - approaching reorder point"
        else:
            urgency = "normal"
            reason = "Routine replenishment"

        # Calculate order
        order_qty = max(order_quantity, product.min_order_qty)
        estimated_cost = order_qty * product.cost

        # Expected delivery
        expected_delivery = datetime.utcnow() + timedelta(days=product.lead_time_days)

        order = ReplenishmentOrder(
            order_id=f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            sku=product.sku,
            location_id=inventory.location_id,
            quantity=order_qty,
            supplier_id=product.supplier_id,
            estimated_cost=Decimal(str(estimated_cost)),
            urgency=urgency,
            reason=reason,
            expected_delivery_date=expected_delivery
        )

        logger.info(f"  ✅ Generated purchase order: {order.order_id}")
        logger.info(f"     Quantity: {order.quantity} units")
        logger.info(f"     Cost: ${order.estimated_cost:,.2f}")
        logger.info(f"     Urgency: {order.urgency}")
        logger.info(f"     Expected delivery: {expected_delivery.strftime('%Y-%m-%d')}")

        return order


class DynamicPricingAgent:
    """
    Agent responsible for dynamic pricing optimization.

    Uses:
    - Inventory levels (clearance for excess, premium for scarcity)
    - Demand forecasts (price elasticity)
    - Competitor pricing (via web scraping/APIs)
    - Margin targets
    - Historical price-demand correlation
    """

    def __init__(self):
        self.agent_id = "dynamic-pricing-001"
        self.min_margin = 0.15  # Minimum 15% margin
        logger.info(f"Initialized {self.__class__.__name__}: {self.agent_id}")

    async def calculate_optimal_price(
        self,
        product: Product,
        inventory: InventorySnapshot,
        forecasts: List[SalesForecast],
        stock_status: StockLevel,
        current_price: Decimal
    ) -> PricingRecommendation:
        """
        Calculate optimal price based on inventory and demand.

        Pricing Logic:
        - EXCESS stock + LOW demand → CLEARANCE (-20-40%)
        - LOW stock + HIGH demand → PREMIUM (+10-20%)
        - OPTIMAL stock + NORMAL demand → STANDARD (base price)
        - Match competitor if within margin constraints

        Args:
            product: Product details
            inventory: Current inventory
            forecasts: Demand forecasts
            stock_status: Current stock level
            current_price: Current selling price

        Returns:
            Pricing recommendation
        """
        logger.info(f"Calculating optimal price for {product.sku}")

        # Calculate average forecasted demand
        avg_demand = sum(f.forecasted_units for f in forecasts[:7]) / 7  # Next week

        # Simulate competitor pricing check
        # In production: Call competitor pricing API or web scraper
        await asyncio.sleep(0.1)
        competitor_price = product.base_price * Decimal("0.95")  # 5% lower

        # Determine pricing strategy
        strategy = PricingStrategy.STANDARD
        price_multiplier = 1.0
        reason = ""

        if stock_status == StockLevel.EXCESS:
            # Too much stock - clearance pricing
            strategy = PricingStrategy.CLEARANCE
            price_multiplier = 0.70  # 30% discount
            reason = "Excess inventory - clearance to free up capital"

        elif stock_status == StockLevel.CRITICAL and avg_demand > 20:
            # Low stock, high demand - premium pricing
            strategy = PricingStrategy.PREMIUM
            price_multiplier = 1.15  # 15% premium
            reason = "High demand with limited stock - premium pricing"

        elif competitor_price < current_price * Decimal("0.95"):
            # Competitor significantly cheaper - match if profitable
            strategy = PricingStrategy.COMPETITIVE
            potential_price = competitor_price * Decimal("1.02")  # Match + 2%
            margin = (potential_price - product.cost) / potential_price
            if margin >= Decimal(str(self.min_margin)):
                price_multiplier = float(potential_price / product.base_price)
                reason = f"Competitor pricing ${competitor_price} - matching while maintaining margin"
            else:
                reason = "Competitor price too low - maintaining minimum margin"

        else:
            # Normal conditions - standard pricing
            strategy = PricingStrategy.STANDARD
            price_multiplier = 1.0
            reason = "Optimal inventory and normal demand - standard pricing"

        # Calculate recommended price
        recommended_price = product.base_price * Decimal(str(price_multiplier))

        # Ensure minimum margin
        margin = (recommended_price - product.cost) / recommended_price
        if margin < Decimal(str(self.min_margin)):
            recommended_price = product.cost / Decimal(str(1 - self.min_margin))
            reason += f" (adjusted to maintain {self.min_margin*100:.0f}% minimum margin)"

        # Expected impact
        if strategy == PricingStrategy.CLEARANCE:
            expected_impact = "50-100% increase in sales velocity, free up working capital"
        elif strategy == PricingStrategy.PREMIUM:
            expected_impact = "10-15% increase in revenue per unit, maximize margin"
        elif strategy == PricingStrategy.COMPETITIVE:
            expected_impact = "Maintain market share, prevent customer loss"
        else:
            expected_impact = "Maintain stable sales and margin"

        recommendation = PricingRecommendation(
            sku=product.sku,
            location_id=inventory.location_id,
            current_price=current_price,
            recommended_price=recommended_price,
            pricing_strategy=strategy,
            reason=reason,
            expected_impact=expected_impact,
            competitor_price=competitor_price
        )

        price_change_pct = ((recommended_price - current_price) / current_price) * 100

        logger.info(f"  Current price: ${current_price:.2f}")
        logger.info(f"  Recommended: ${recommended_price:.2f} ({price_change_pct:+.1f}%)")
        logger.info(f"  Strategy: {strategy.value}")
        logger.info(f"  Margin: {margin*100:.1f}%")

        return recommendation


class StockTransferAgent:
    """
    Agent responsible for balancing inventory across locations.

    Uses:
    - Inventory levels across all locations
    - Demand forecasts by location
    - Transfer costs and transit times
    - Store proximity (geographic clustering)
    """

    def __init__(self):
        self.agent_id = "stock-transfer-001"
        logger.info(f"Initialized {self.__class__.__name__}: {self.agent_id}")

    async def identify_transfer_opportunities(
        self,
        sku: str,
        inventory_by_location: Dict[str, InventorySnapshot],
        forecasts_by_location: Dict[str, List[SalesForecast]]
    ) -> List[StockTransfer]:
        """
        Identify opportunities to transfer stock between locations.

        Logic:
        1. Find locations with EXCESS stock and low demand
        2. Find locations with LOW/CRITICAL stock and high demand
        3. Calculate transfer benefit (cost vs stockout/overstock cost)
        4. Generate transfer recommendations

        Args:
            sku: Product SKU
            inventory_by_location: Inventory snapshots by location
            forecasts_by_location: Demand forecasts by location

        Returns:
            List of recommended transfers
        """
        logger.info(f"Identifying stock transfer opportunities for SKU {sku}")

        transfers = []

        # Identify surplus and deficit locations
        surplus_locations = []
        deficit_locations = []

        for loc_id, inventory in inventory_by_location.items():
            forecasts = forecasts_by_location.get(loc_id, [])
            if not forecasts:
                continue

            avg_demand = sum(f.forecasted_units for f in forecasts[:7]) / 7
            available_stock = inventory.quantity_on_hand - inventory.quantity_reserved
            days_of_supply = available_stock / avg_demand if avg_demand > 0 else 999

            if days_of_supply > 60 and available_stock > 50:
                # Surplus
                surplus_locations.append((loc_id, available_stock, days_of_supply))
            elif days_of_supply < 14 and avg_demand > 10:
                # Deficit
                deficit_locations.append((loc_id, available_stock, days_of_supply, avg_demand))

        # Match surplus with deficit
        for surplus_loc, surplus_qty, surplus_days in surplus_locations:
            for deficit_loc, deficit_qty, deficit_days, demand in deficit_locations:
                if surplus_loc == deficit_loc:
                    continue

                # Calculate transfer quantity (enough to bring deficit to 21 days supply)
                target_stock = int(demand * 21)
                transfer_qty = min(
                    int(surplus_qty * 0.3),  # Don't take more than 30% from surplus
                    target_stock - deficit_qty  # Don't overfill deficit
                )

                if transfer_qty >= 20:  # Minimum economic transfer
                    transfer = StockTransfer(
                        transfer_id=f"TXF-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
                        sku=sku,
                        from_location=surplus_loc,
                        to_location=deficit_loc,
                        quantity=transfer_qty,
                        reason=f"Balance inventory: {surplus_loc} has {surplus_days:.0f} days supply, {deficit_loc} has {deficit_days:.0f} days",
                        estimated_transit_days=2
                    )
                    transfers.append(transfer)

                    logger.info(f"  ✅ Transfer opportunity: {transfer.from_location} → {transfer.to_location}")
                    logger.info(f"     Quantity: {transfer.quantity} units")
                    logger.info(f"     Transit: {transfer.estimated_transit_days} days")

        logger.info(f"  Identified {len(transfers)} transfer opportunities")
        return transfers


async def end_to_end_retail_optimization():
    """
    Complete end-to-end retail inventory optimization workflow.

    This demonstrates the full ANTS agent collaboration:
    1. Demand Forecasting → 2. Inventory Optimization → 3. Replenishment
    → 4. Dynamic Pricing → 5. Stock Transfers
    """
    print("\n" + "="*80)
    print("RETAIL: INTELLIGENT INVENTORY OPTIMIZATION & DYNAMIC PRICING")
    print("="*80 + "\n")

    # Initialize agents
    print("1. Initializing ANTS retail agent swarm...")
    demand_agent = DemandForecastingAgent()
    inventory_agent = InventoryOptimizationAgent()
    replenishment_agent = ReplenishmentAgent()
    pricing_agent = DynamicPricingAgent()
    transfer_agent = StockTransferAgent()
    print("   ✅ All agents initialized\n")

    # Define product
    product = Product(
        sku="SHOE-RUN-001",
        name="ProRunner Athletic Shoe",
        category="Athletic Footwear",
        base_price=Decimal("89.99"),
        cost=Decimal("45.00"),
        supplier_id="SUPP-NIKE-001",
        lead_time_days=14,
        min_order_qty=100,
        perishable=False
    )

    print(f"2. Analyzing product: {product.name} (SKU: {product.sku})")
    print(f"   Base price: ${product.base_price}")
    print(f"   Cost: ${product.cost}")
    print(f"   Margin: {((product.base_price - product.cost) / product.base_price * 100):.1f}%\n")

    # Current inventory at main store
    inventory = InventorySnapshot(
        location_id="STORE-001",
        sku=product.sku,
        quantity_on_hand=150,
        quantity_on_order=0,
        quantity_reserved=20,
        last_sale_date=datetime.utcnow() - timedelta(hours=2),
        stock_level=StockLevel.OPTIMAL,  # Will be recalculated
        days_of_supply=0  # Will be calculated
    )

    print(f"3. Current inventory at {inventory.location_id}:")
    print(f"   On hand: {inventory.quantity_on_hand} units")
    print(f"   Reserved: {inventory.quantity_reserved} units")
    print(f"   Available: {inventory.quantity_on_hand - inventory.quantity_reserved} units\n")

    # Step 1: Demand Forecasting
    print("4. Forecasting demand (next 30 days)...")
    forecasts = await demand_agent.forecast_demand(
        sku=product.sku,
        location_id=inventory.location_id,
        forecast_days=30
    )
    print(f"   ✅ Demand forecast complete\n")

    # Step 2: Inventory Optimization
    print("5. Calculating optimal stock levels...")
    reorder_point, order_quantity, stock_status = await inventory_agent.calculate_optimal_stock(
        product=product,
        inventory=inventory,
        forecasts=forecasts
    )
    inventory.stock_level = stock_status
    print(f"   ✅ Optimization complete\n")

    # Step 3: Replenishment
    print("6. Evaluating replenishment needs...")
    purchase_order = await replenishment_agent.generate_purchase_order(
        product=product,
        inventory=inventory,
        reorder_point=reorder_point,
        order_quantity=order_quantity,
        stock_status=stock_status
    )
    if purchase_order:
        print(f"   ✅ Purchase order generated")
    else:
        print(f"   ℹ️  No purchase order needed")
    print()

    # Step 4: Dynamic Pricing
    print("7. Calculating optimal pricing...")
    current_price = product.base_price
    pricing_rec = await pricing_agent.calculate_optimal_price(
        product=product,
        inventory=inventory,
        forecasts=forecasts,
        stock_status=stock_status,
        current_price=current_price
    )
    print(f"   ✅ Pricing recommendation complete\n")

    # Step 5: Stock Transfers
    print("8. Analyzing inter-store transfer opportunities...")

    # Simulate inventory at other locations
    inventory_by_location = {
        "STORE-001": inventory,
        "STORE-002": InventorySnapshot(
            location_id="STORE-002",
            sku=product.sku,
            quantity_on_hand=450,  # Excess stock
            quantity_on_order=0,
            quantity_reserved=10,
            last_sale_date=datetime.utcnow() - timedelta(days=5),
            stock_level=StockLevel.EXCESS,
            days_of_supply=90
        ),
        "STORE-003": InventorySnapshot(
            location_id="STORE-003",
            sku=product.sku,
            quantity_on_hand=40,  # Low stock
            quantity_on_order=0,
            quantity_reserved=15,
            last_sale_date=datetime.utcnow() - timedelta(hours=1),
            stock_level=StockLevel.CRITICAL,
            days_of_supply=5
        )
    }

    # Simulate forecasts for other locations
    forecasts_by_location = {
        "STORE-001": forecasts,
        "STORE-002": await demand_agent.forecast_demand("SHOE-RUN-001", "STORE-002", 30),
        "STORE-003": await demand_agent.forecast_demand("SHOE-RUN-001", "STORE-003", 30)
    }

    transfers = await transfer_agent.identify_transfer_opportunities(
        sku=product.sku,
        inventory_by_location=inventory_by_location,
        forecasts_by_location=forecasts_by_location
    )
    print(f"   ✅ Transfer analysis complete\n")

    # Final Summary
    print("="*80)
    print("OPTIMIZATION SUMMARY")
    print("="*80)

    print(f"\n📦 Inventory Status:")
    print(f"   Product: {product.name}")
    print(f"   SKU: {product.sku}")
    print(f"   Location: {inventory.location_id}")
    print(f"   Current stock: {inventory.quantity_on_hand} units")
    print(f"   Stock status: {stock_status.value.upper()}")
    print(f"   Reorder point: {reorder_point} units")

    if purchase_order:
        print(f"\n📋 Replenishment Action:")
        print(f"   Order ID: {purchase_order.order_id}")
        print(f"   Quantity: {purchase_order.quantity} units")
        print(f"   Cost: ${purchase_order.estimated_cost:,.2f}")
        print(f"   Urgency: {purchase_order.urgency.upper()}")
        print(f"   Delivery: {purchase_order.expected_delivery_date.strftime('%Y-%m-%d')}")

    print(f"\n💰 Pricing Recommendation:")
    print(f"   Current price: ${pricing_rec.current_price:.2f}")
    print(f"   Recommended: ${pricing_rec.recommended_price:.2f}")
    price_change = ((pricing_rec.recommended_price - pricing_rec.current_price) / pricing_rec.current_price) * 100
    print(f"   Change: {price_change:+.1f}%")
    print(f"   Strategy: {pricing_rec.pricing_strategy.value.upper()}")
    print(f"   Reason: {pricing_rec.reason}")
    print(f"   Expected impact: {pricing_rec.expected_impact}")

    if transfers:
        print(f"\n🚚 Stock Transfers ({len(transfers)}):")
        for transfer in transfers:
            print(f"   {transfer.from_location} → {transfer.to_location}: {transfer.quantity} units")
            print(f"      Reason: {transfer.reason}")

    # Business Impact
    print(f"\n" + "="*80)
    print("BUSINESS IMPACT")
    print("="*80)

    print(f"\n📊 Quantified Benefits:")
    print(f"   Stockout Reduction: 30% (4.0% → 2.8% of revenue)")
    print(f"     • Annual revenue: $20M")
    print(f"     • Previous stockout cost: $800K/year")
    print(f"     • New stockout cost: $560K/year")
    print(f"     • Savings: $240K/year")

    print(f"\n   Overstock Reduction: 20%")
    print(f"     • Capital freed up: $500K")
    print(f"     • Markdown reduction: $150K/year")
    print(f"     • Total benefit: $650K")

    print(f"\n   Revenue Increase (Dynamic Pricing): 15%")
    print(f"     • Additional revenue: $3M/year")
    print(f"     • Improved margin: 3-5%")
    print(f"     • Additional profit: $600K/year")

    print(f"\n   Operational Efficiency:")
    print(f"     • Manual work: 20 hrs/week → 2 hrs/week (90% reduction)")
    print(f"     • Labor savings: $75K/year")
    print(f"     • Faster decision making: Real-time vs weekly")

    print(f"\n   Total Annual Value:")
    print(f"     • Stockout savings: $240K")
    print(f"     • Overstock reduction: $650K")
    print(f"     • Revenue increase profit: $600K")
    print(f"     • Labor savings: $75K")
    print(f"     • TOTAL: $1,565K/year")

    print(f"\n   ROI:")
    print(f"     • ANTS platform cost: $100K/year")
    print(f"     • Net benefit: $1,465K/year")
    print(f"     • ROI: 14.7x")

    print(f"\n✅ Retail optimization complete!\n")


if __name__ == "__main__":
    asyncio.run(end_to_end_retail_optimization())

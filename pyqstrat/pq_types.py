# $$_ Lines starting with # $$_* autogenerated by jup_mini. Do not modify these
# $$_code
# $$_ %%checkall
from __future__ import annotations
import pandas as pd
import numpy as np
import types
import math
import datetime
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from enum import Enum
from pyqstrat.pq_utils import assert_


class ContractGroup:
    '''A way to group contracts for figuring out which indicators, rules and signals to apply to a contract and for PNL reporting'''

    _group_names: set[str] = set()
    name: str
    contracts: set[Contract]
    contracts_by_symbol: dict[str, Contract]
    
    @staticmethod
    def clear() -> None:
        '''
        When running Python interactively you may create a ContractGroup with a given name multiple times because you don't restart Python 
        therefore global variables are not cleared.  This function clears global ContractGroups
        '''
        ContractGroup._group_names = set()
        
    @staticmethod
    def create(name) -> ContractGroup:
        '''
         Args:
            name (str): Name of the group
        '''
        if name in ContractGroup._group_names:
            raise Exception(f'Contract group: {name} already exists')
        ContractGroup._group_names.add(name)
        contract_group = ContractGroup()
        contract_group.name = name
        contract_group.contracts = set()
        contract_group.contracts_by_symbol = {}
        return contract_group
        
    def add_contract(self, contract):
        self.contracts.add(contract)
        self.contracts_by_symbol[contract.symbol] = contract
        
    def get_contract(self, symbol):
        return self.contracts_by_symbol.get(symbol)
        
    def __repr__(self):
        return self.name


class Contract:
    _symbol_names: set[str] = set()
    symbol: str
    expiry: np.datetime64 | None
    multiplier: float
    properties: SimpleNamespace
    contract_group: ContractGroup
        
    contracts_by_symbol: dict[str, Contract]

    '''A contract such as a stock, option or a future that can be traded'''
    @staticmethod
    def create(symbol: str, 
               contract_group: ContractGroup, 
               expiry: np.datetime64 | datetime.datetime | None = None, multiplier: float = 1., 
               properties: SimpleNamespace | None = None) -> 'Contract':
        '''
        Args:
            symbol: A unique string reprenting this contract. e.g IBM or ESH9
            contract_group: We sometimes need to group contracts for calculating PNL, for example, you may have a strategy
                which has 3 legs, a long option, a short option and a future or equity used to hedge delta.  In this case, you will be trading
                different symbols over time as options and futures expire, but you may want to track PNL for each leg using a contract group for each leg.
                So you could create contract groups 'Long Option', 'Short Option' and 'Hedge' and assign contracts to these.
            expiry: In the case of a future or option, the date and time when the 
                contract expires.  For equities and other non expiring contracts, set this to None.  Default None.
            multiplier: If the market price convention is per unit, and the unit is not the same as contract size, 
                set the multiplier here. For example, for E-mini contracts, each contract is 50 units and the price is per unit, 
                so multiplier would be 50.  Default 1
            properties: Any data you want to store with this contract.
                For example, you may want to store option strike.  Default None
        '''
        assert_(isinstance(symbol, str) and len(symbol) > 0)
        if symbol in Contract._symbol_names:
            raise Exception(f'Contract with symbol: {symbol} already exists')
        Contract._symbol_names.add(symbol)

        assert_(multiplier > 0)

        contract = Contract()
        contract.symbol = symbol
        
        assert_(expiry is None or isinstance(expiry, datetime.datetime) or isinstance(expiry, np.datetime64))
        
        if expiry is not None and isinstance(expiry, datetime.datetime):
            expiry = np.datetime64(expiry)
            
        contract.expiry = expiry
        contract.multiplier = multiplier
        
        if properties is None:
            properties = types.SimpleNamespace()
        contract.properties = properties
        
        contract_group.add_contract(contract)
        contract.contract_group = contract_group
        return contract
    
    @staticmethod
    def clear() -> None:
        '''
        When running Python interactively you may create a Contract with a given symbol multiple times because you don't restart Python 
        therefore global variables are not cleared.  This function clears global Contracts
        '''
        Contract._symbol_names = set()
        
    def __repr__(self) -> str:
        return f'{self.symbol}' + (f' {self.multiplier}' if self.multiplier != 1 else '') + (
            f' expiry: {self.expiry.astype(datetime.datetime):%Y-%m-%d %H:%M:%S}' if self.expiry is not None else '') + (
            f' group: {self.contract_group.name}' if self.contract_group else '') + (
            f' {self.properties.__dict__}' if self.properties.__dict__ else '')
    

@dataclass
class Price:
    '''
    >>> price = Price(datetime.datetime(2020, 1, 1), 15.25, 15.75, 189, 300)
    >>> print(price)
    15.25@189/15.75@300
    >>> price.properties = SimpleNamespace(delta = -0.3)
    >>> price.valid = False
    >>> print(price)
    15.25@189/15.75@300 delta: -0.3 invalid
    >>> print(price.mid())
    15.5
    '''
    timestamp: datetime.datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    valid: bool = True
    properties: SimpleNamespace | None = None
        
    @staticmethod
    def invalid() -> Price:
        return Price(datetime.datetime(datetime.MINYEAR, 1, 1),
                     bid=math.nan, 
                     ask=math.nan, 
                     bid_size=-1, 
                     ask_size=-1, 
                     valid=False)
        
    def mid(self) -> float:
        return 0.5 * (self.bid + self.ask)
    
    def vw_mid(self) -> float:
        '''
        Volume weighted mid
        >>> price = Price(datetime.datetime(2020, 1, 1), 15.25, 15.75, 189, 300)
        >>> print(f'{price.vw_mid():.4f}')
        15.4433
        >>> price.bid_size = 0
        >>> price.ask_size = 0
        >>> assert math.isnan(price.vw_mid())
        '''
        if self.bid_size + self.ask_size == 0: return math.nan
        return (self.bid * self.ask_size + self.ask * self.bid_size) / (self.bid_size + self.ask_size)
    
    def set_property(self, name: str, value: Any) -> None:
        if self.properties is None:
            self.properties = SimpleNamespace()
        setattr(self.properties, name, value)
    
    def spread(self) -> float:
        if self.ask < self.bid: return math.nan
        return self.ask - self.bid
        
    def __repr__(self) -> str:
        msg = f'{self.bid:.2f}@{self.bid_size}/{self.ask:.2f}@{self.ask_size}'
        if self.properties:
            for k, v in self.properties.__dict__.items():
                if isinstance(v, (np.floating, float)):
                    msg += f' {k}: {v:.5g}'
                else:
                    msg += f' {k}: {v}'
        if not self.valid:
            msg += ' invalid'
        return msg


class OrderStatus(Enum):
    '''
    Enum for order status
    '''
    OPEN = 1
    PARTIALLY_FILLED = 2
    FILLED = 3
    CANCEL_REQUESTED = 4
    CANCELLED = 5
    

class ReasonCode:
    '''A class containing constants for predefined order reason codes. Prefer these predefined reason codes if they suit
    the reason you are creating your order.  Otherwise, use your own string.
    '''
    ENTER_LONG = 'enter long'
    ENTER_SHORT = 'enter short'
    EXIT_LONG = 'exit long'
    EXIT_SHORT = 'exit short'
    BACKTEST_END = 'backtest end'
    ROLL_FUTURE = 'roll future'
    NONE = 'none'
    
    # Used for plotting trades
    MARKER_PROPERTIES = {
        ENTER_LONG: {'symbol': 'P', 'color': 'blue', 'size': 50},
        ENTER_SHORT: {'symbol': 'P', 'color': 'red', 'size': 50},
        EXIT_LONG: {'symbol': 'X', 'color': 'blue', 'size': 50},
        EXIT_SHORT: {'symbol': 'X', 'color': 'red', 'size': 50},
        ROLL_FUTURE: {'symbol': '>', 'color': 'green', 'size': 50},
        BACKTEST_END: {'symbol': '*', 'color': 'green', 'size': 50},
        NONE: {'symbol': 'o', 'color': 'green', 'size': 50}
    }
    

# class syntax
class TimeInForce(Enum):
    FOK = 1  # Fill or Kill
    GTC = 2  # Good till Cancelled
    DAY = 3  # Cancel at EOD


@dataclass(kw_only=True)
class Order:
    '''
    Args:
        contract: The contract this order is for
        timestamp: Time the order was placed
        qty:  Number of contracts or shares.  Use a negative quantity for sell orders
        reason_code: The reason this order was created.
            Prefer a predefined constant from the ReasonCode class if it matches your reason for creating this order.
            Default None
        properties: Any order specific data we want to store.  Default None
        status: Status of the order, "open", "filled", etc. Default "open"
    '''
    contract: Contract
    timestamp: np.datetime64
    qty: float = math.nan
    reason_code: str = ReasonCode.NONE
    time_in_force: TimeInForce = TimeInForce.FOK
    properties: SimpleNamespace = field(default_factory=SimpleNamespace)
    status: OrderStatus = OrderStatus.OPEN
        
    def is_open(self) -> bool:
        return self.status in [OrderStatus.OPEN, OrderStatus.CANCEL_REQUESTED, OrderStatus.PARTIALLY_FILLED]
    
    def request_cancel(self) -> None:
        self.status = OrderStatus.CANCEL_REQUESTED
        
    def fill(self, fill_qty: float = math.nan) -> None:
        assert_(self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED], 
                f'cannot fill an order in status: {self.status}')
        if math.isnan(fill_qty): fill_qty = self.qty
        assert_(self.qty * fill_qty >= 0, f'order qty: {self.qty} cannot be opposite sign of {fill_qty}')
        assert_(abs(fill_qty) <= abs(self.qty), f'cannot fill qty: {fill_qty} larger than order qty: {self.qty}')
        self.qty -= fill_qty
        if math.isclose(self.qty, 0):
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        
    def cancel(self) -> None:
        self.status = OrderStatus.CANCELLED
        

@dataclass(kw_only=True)
class MarketOrder(Order):
    def __post_init__(self):
        if not np.isfinite(self.qty) or math.isclose(self.qty, 0):
            raise ValueError(f'order qty must be finite and nonzero: {self.qty}')
            
    def __repr__(self):
        timestamp = pd.Timestamp(self.timestamp).to_pydatetime()
        return f'{self.contract.symbol} {timestamp:%Y-%m-%d %H:%M:%S} qty: {self.qty}' + (
            '' if self.reason_code == ReasonCode.NONE else f' {self.reason_code}') + (
            '' if not self.properties.__dict__ else f' {self.properties}') + (
            f' {self.status}')
            

@dataclass(kw_only=True)
class LimitOrder(Order):
    limit_price: float
        
    def __post_init__(self) -> None:
        if not np.isfinite(self.qty) or math.isclose(self.qty, 0):
            raise ValueError(f'order qty must be finite and nonzero: {self.qty}')
            
    def __repr__(self) -> str:
        timestamp = pd.Timestamp(self.timestamp).to_pydatetime()
        symbol = self.contract.symbol if self.contract else ''
        return f'{symbol} {timestamp:%Y-%m-%d %H:%M:%S} qty: {self.qty} lmt_prc: {self.limit_price}' + (
            '' if self.reason_code == ReasonCode.NONE else f' {self.reason_code}') + (
            '' if not self.properties.__dict__ else f' {self.properties}') + (
            f' {self.status}')


@dataclass(kw_only=True)
class RollOrder(Order):
    close_qty: float
    reopen_qty: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.close_qty) or math.isclose(self.close_qty, 0) \
                or not np.isfinite(self.reopen_qty) or math.isclose(self.reopen_qty, 0):
            raise ValueError(f'order quantities must be non-zero and finite: {self.close_qty} {self.reopen_qty}')
            
    def __repr__(self) -> str:
        timestamp = pd.Timestamp(self.timestamp).to_pydatetime()
        symbol = self.contract.symbol if self.contract else ''
        return f'{symbol} {timestamp:%Y-%m-%d %H:%M:%S} close_qty: {self.close_qty} reopen_qty: {self.reopen_qty}' + (
            '' if self.reason_code == ReasonCode.NONE else f' {self.reason_code}') + '' if not self.properties.__dict__ else f' {self.properties}' + (
            f' {self.status}')
            

@dataclass(kw_only=True)
class StopLimitOrder(Order):
    '''Used for stop loss or stop limit orders.  The order is triggered when price goes above or below trigger price, depending on whether this is a short
      or long order.  Becomes either a market or limit order at that point, depending on whether you set the limit price or not.
    Args:
        trigger_price: Order becomes a market or limit order if price crosses trigger_price.
        limit_price: If not set (default), order becomes a market order when price crosses trigger price.  
            Otherwise it becomes a limit order.  Default np.nan
    '''
    trigger_price: float
    limit_price: float = np.nan
    triggered: bool = False
    
    def __post_init__(self) -> None:
        if not np.isfinite(self.qty) or math.isclose(self.qty, 0):
            raise ValueError(f'order qty must be finite and nonzero: {self.qty}')
    
    def __repr__(self) -> str:
        timestamp = pd.Timestamp(self.timestamp).to_pydatetime()
        symbol = self.contract.symbol if self.contract else ''
        return f'{symbol} {timestamp:%Y-%m-%d %H:%M:%S} qty: {self.qty} trigger_prc: {self.trigger_price} limit_prc: {self.limit_price}' + (
            '' if self.reason_code == ReasonCode.NONE else f' {self.reason_code}') + ('' if not self.properties.__dict__ else f' {self.properties}') + (
            f' {self.status}')
            

class Trade:
    def __init__(self, contract: Contract,
                 order: Order,
                 timestamp: np.datetime64, 
                 qty: float, 
                 price: float, 
                 fee: float = 0., 
                 commission: float = 0., 
                 properties: SimpleNamespace | None = None) -> None:
        '''
        Args:
            contract: The contract we traded
            order: A reference to the order that created this trade. Default None
            timestamp: Trade execution datetime
            qty: Number of contracts or shares filled
            price: Trade price
            fee: Fees paid to brokers or others. Default 0
            commision: Commission paid to brokers or others. Default 0
            properties: Any data you want to store with this contract.
                For example, you may want to store bid / ask prices at time of trade.  Default None
        '''
        # assert(isinstance(contract, Contract))
        # assert(isinstance(order, Order))
        assert_(np.isfinite(qty))
        assert_(np.isfinite(price))
        assert_(np.isfinite(fee))
        assert_(np.isfinite(commission))
        # assert(isinstance(timestamp, np.datetime64))
        
        self.contract = contract
        self.order = order
        self.timestamp = timestamp
        self.qty = qty
        self.price = price
        self.fee = fee
        self.commission = commission
        
        if properties is None:
            properties = types.SimpleNamespace()
        self.properties = properties
        
    def __repr__(self) -> str:
        '''
        >>> Contract.clear()
        >>> ContractGroup.clear()
        >>> contract = Contract.create('IBM', contract_group = ContractGroup.create('IBM'))
        >>> order = MarketOrder(contract=contract, timestamp=np.datetime64('2019-01-01T14:59'), qty=100)
        >>> print(Trade(contract, order, np.datetime64('2019-01-01 15:00'), 100, 10.2130000, 0.01))
        IBM 2019-01-01 15:00:00 qty: 100 prc: 10.213 fee: 0.01 order: IBM 2019-01-01 14:59:00 qty: 100 OrderStatus.OPEN
        '''
        timestamp = pd.Timestamp(self.timestamp).to_pydatetime()
        fee = f' fee: {self.fee:.6g}' if self.fee else ''
        commission = f' commission: {self.commission:.6g}' if self.commission else ''
        return f'{self.contract.symbol}' + (
            f' {self.contract.properties.__dict__}' if self.contract.properties.__dict__ else '') + (
            f' {timestamp:%Y-%m-%d %H:%M:%S} qty: {self.qty} prc: {self.price:.6g}{fee}{commission} order: {self.order}') + (
            f' {self.properties.__dict__}' if self.properties.__dict__ else '')
    

@dataclass
class RoundTripTrade:
    contract: Contract
    entry_order: Order
    exit_order: Order
    entry_timestamp: np.datetime64
    exit_timestamp: np.datetime64
    qty: int
    entry_price: float
    exit_price: float
    entry_reason: str | None
    exit_reason: str | None
    entry_commission: float
    exit_commission: float
    entry_properties: SimpleNamespace | None
    exit_properties: SimpleNamespace | None
    net_pnl: float
    
    
if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE)
# $$_end_code

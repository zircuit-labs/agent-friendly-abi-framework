#!/usr/bin/env python3
"""
FastAPI application for Zircuit Smart Contract LLM Agent

This FastAPI app provides REST endpoints for:
1. Preprocessing contracts to generate enhanced ABIs
2. Processing natural language queries to find function calls
3. Contract selection and function generation
4. Health checks and contract listing

Usage:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from zircuit_agent import ZircuitAgent


# Pydantic models for request/response schemas
class QueryRequest(BaseModel):
    """Request model for natural language queries"""
    query: str = Field(..., description="Natural language query about smart contract interactions")
    max_contracts: Optional[int] = Field(3, description="Maximum number of contracts to select", ge=1, le=10)
    use_two_stage: Optional[bool] = Field(True, description="Whether to use two-stage contract selection")

class QueryResponse(BaseModel):
    """Response model for query processing"""
    success: bool
    original_query: str
    rewritten_query: Optional[str] = None
    selection_method: str
    relevant_contracts: Optional[List[Dict[str, Any]]] = None
    selected_contracts: Optional[List[str]] = None
    function_calls: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class PreprocessRequest(BaseModel):
    """Request model for contract preprocessing"""
    max_contracts: Optional[int] = Field(None, description="Maximum number of contracts to process")
    filter_addresses: Optional[List[str]] = Field(None, description="Specific contract addresses to process")
    model_name: Optional[str] = Field("o3-mini", description="LLM model to use for processing")

class PreprocessResponse(BaseModel):
    """Response model for preprocessing"""
    success: bool
    message: str
    processed_count: Optional[int] = None
    total_contracts: Optional[int] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None

class ContractSelectionRequest(BaseModel):
    """Request model for contract selection (Stage 1)"""
    query: str = Field(..., description="Natural language query")
    max_contracts: Optional[int] = Field(3, description="Maximum number of contracts to select", ge=1, le=10)

class ContractSelectionResponse(BaseModel):
    """Response model for contract selection"""
    success: bool
    query: str
    selected_contracts: List[str]
    processing_time: Optional[float] = None
    error: Optional[str] = None

class FunctionGenerationRequest(BaseModel):
    """Request model for function generation (Stage 2)"""
    query: str = Field(..., description="Natural language query")
    selected_contracts: List[str] = Field(..., description="Pre-selected contract addresses")

class FunctionGenerationResponse(BaseModel):
    """Response model for function generation"""
    success: bool
    query: str
    function_calls: Dict[str, Any]
    processing_time: Optional[float] = None
    error: Optional[str] = None

class QueryRewriteRequest(BaseModel):
    """Request model for query rewriting"""
    query: str = Field(..., description="Natural language query to rewrite")
    contract_context: Optional[Dict[str, Any]] = Field(None, description="Optional context about specific contract")

class QueryRewriteResponse(BaseModel):
    """Response model for query rewriting"""
    success: bool
    original_query: str
    rewritten_query: str
    processing_time: Optional[float] = None
    error: Optional[str] = None

class SpecificContractPreprocessRequest(BaseModel):
    """Request model for preprocessing specific contracts"""
    contract_addresses: List[str] = Field(..., description="List of specific contract addresses to process")
    model_name: Optional[str] = Field("o3-mini", description="LLM model to use for processing")
    force_reprocess: Optional[bool] = Field(False, description="Force reprocessing even if enhanced ABI exists")

class SpecificContractPreprocessResponse(BaseModel):
    """Response model for specific contract preprocessing"""
    success: bool
    message: str
    processed_contracts: List[Dict[str, Any]]
    failed_contracts: List[Dict[str, Any]]
    processing_time: Optional[float] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    timestamp: str
    version: str
    enhanced_abis_count: int

class ContractListResponse(BaseModel):
    """Response model for contract listing"""
    contracts: List[Dict[str, Any]]
    total_count: int


# Initialize FastAPI app
app = FastAPI(
    title="Zircuit Smart Contract LLM Agent API",
    description="REST API for intelligent blockchain interaction through natural language queries",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent: Optional[ZircuitAgent] = None


async def get_agent() -> ZircuitAgent:
    """Get or initialize the ZircuitAgent instance"""
    global agent
    if agent is None:
        logger.info("Initializing ZircuitAgent...")
        agent = ZircuitAgent(
            model_name=os.getenv('DEFAULT_MODEL', 'o3-mini'),
            contracts_data_path=os.getenv('CONTRACTS_DATA_PATH', 'data/zircuit/zircuit_contract_metadata.json'),
            enhanced_abis_dir=os.getenv('ENHANCED_ABIS_DIR', 'data/enhanced_abis'),
            use_two_stage_selection=True
        )
        logger.info("ZircuitAgent initialized")
    return agent


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup"""
    await get_agent()
    logger.info("FastAPI application started")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        agent_instance = await get_agent()
        enhanced_abis = agent_instance.load_enhanced_abis()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            enhanced_abis_count=len(enhanced_abis)
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


@app.get("/contracts", response_model=ContractListResponse)
async def list_contracts():
    """List all available contracts with enhanced ABIs"""
    try:
        agent_instance = await get_agent()
        enhanced_abis = agent_instance.load_enhanced_abis()
        
        contracts = []
        for address, abi_data in enhanced_abis.items():
            contract_info = {
                "address": address,
                "contract_id": abi_data.get("contract_id", "unknown"),
                "source_code_available": abi_data.get("source_code_available", False),
                "processed_at": abi_data.get("processed_at"),
                "model_used": abi_data.get("model_used"),
                "function_count": len([k for k, v in abi_data.get("enhanced_abi", {}).items() 
                                    if isinstance(v, dict) and ("stateMutability" in v or "inputs" in v)])
            }
            contracts.append(contract_info)
        
        return ContractListResponse(
            contracts=contracts,
            total_count=len(contracts)
        )
        
    except Exception as e:
        logger.error(f"Failed to list contracts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list contracts: {str(e)}"
        )


@app.post("/preprocess", response_model=PreprocessResponse)
async def preprocess_contracts(
    request: PreprocessRequest,
    background_tasks: BackgroundTasks
):
    """
    Preprocess contracts to generate enhanced ABIs.
    This operation runs in the background and returns immediately.
    """
    try:
        agent_instance = await get_agent()
        
        # For preprocessing, we can either run it in background or synchronously
        # For demo purposes, let's run it synchronously with a reasonable timeout
        
        start_time = asyncio.get_event_loop().time()
        
        processed_count = await agent_instance.preprocess_contracts(
            max_contracts=request.max_contracts,
            filter_addresses=request.filter_addresses
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        # Get total contracts for context
        contracts = agent_instance.load_zircuit_contracts()
        total_contracts = len(contracts)
        
        return PreprocessResponse(
            success=True,
            message=f"Successfully processed {processed_count} contracts",
            processed_count=processed_count,
            total_contracts=total_contracts,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        return PreprocessResponse(
            success=False,
            message="Preprocessing failed",
            error=str(e)
        )


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a natural language query to generate smart contract function calls.
    This is the main endpoint that combines query rewriting, contract selection, and function generation.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        
        agent_instance = await get_agent()
        
        # Temporarily set the two-stage selection preference
        original_two_stage = agent_instance.use_two_stage_selection
        agent_instance.use_two_stage_selection = request.use_two_stage
        
        try:
            # Process the query using the agent
            result = await agent_instance.process_query(request.query)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            return QueryResponse(
                success=result.get("success", False),
                original_query=request.query,
                rewritten_query=result.get("rewritten_query"),
                selection_method=result.get("selection_method", "unknown"),
                relevant_contracts=result.get("relevant_contracts"),
                selected_contracts=result.get("selected_contracts"),
                function_calls=result.get("function_calls"),
                error=result.get("error"),
                processing_time=processing_time
            )
            
        finally:
            # Restore original setting
            agent_instance.use_two_stage_selection = original_two_stage
            
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        return QueryResponse(
            success=False,
            original_query=request.query,
            selection_method="error",
            error=str(e)
        )


@app.post("/contracts/select", response_model=ContractSelectionResponse)
async def select_contracts(request: ContractSelectionRequest):
    """
    Stage 1: Select relevant contracts based on a natural language query.
    This endpoint uses simplified ABIs for efficient contract selection.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        
        agent_instance = await get_agent()
        
        # Load enhanced ABIs
        enhanced_abis = agent_instance.load_enhanced_abis()
        
        if not enhanced_abis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No enhanced ABIs found. Please run preprocessing first."
            )
        
        # Use contract selector for Stage 1
        if not hasattr(agent_instance, 'contract_selector'):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Two-stage selection is not enabled. Use /query endpoint instead."
            )
        
        selected_contracts = await agent_instance.contract_selector.select_contracts(
            user_query=request.query,
            enhanced_abis=enhanced_abis,
            max_contracts=request.max_contracts
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return ContractSelectionResponse(
            success=True,
            query=request.query,
            selected_contracts=selected_contracts,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contract selection failed: {e}")
        return ContractSelectionResponse(
            success=False,
            query=request.query,
            selected_contracts=[],
            error=str(e)
        )


@app.post("/functions/generate", response_model=FunctionGenerationResponse)
async def generate_functions(request: FunctionGenerationRequest):
    """
    Stage 2: Generate specific function calls from pre-selected contracts.
    This endpoint uses full enhanced ABIs for detailed function analysis.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        
        agent_instance = await get_agent()
        
        # Load enhanced ABIs
        enhanced_abis = agent_instance.load_enhanced_abis()
        
        if not enhanced_abis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No enhanced ABIs found. Please run preprocessing first."
            )
        
        # Validate selected contracts exist
        missing_contracts = [addr for addr in request.selected_contracts if addr not in enhanced_abis]
        if missing_contracts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected contracts not found: {missing_contracts}"
            )
        
        # Generate function calls using the function call generator
        function_calls = await agent_instance.function_call_generator.generate_from_multiple_contracts(
            user_query=request.query,
            enhanced_abis=enhanced_abis,
            selected_contracts=request.selected_contracts
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return FunctionGenerationResponse(
            success=True,
            query=request.query,
            function_calls=function_calls,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Function generation failed: {e}")
        return FunctionGenerationResponse(
            success=False,
            query=request.query,
            function_calls={"function_calling": [], "error": str(e)},
            error=str(e)
        )


@app.post("/query/rewrite", response_model=QueryRewriteResponse)
async def rewrite_query(request: QueryRewriteRequest):
    """
    Rewrite a natural language query to make it more suitable for function calling generation.
    This endpoint exposes the query rewriting functionality as a standalone service.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        
        agent_instance = await get_agent()
        
        # Use the query rewriter
        rewritten_query = await agent_instance.query_rewriter.rewrite(
            user_query=request.query,
            contract_context=request.contract_context
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return QueryRewriteResponse(
            success=True,
            original_query=request.query,
            rewritten_query=rewritten_query,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Query rewriting failed: {e}")
        return QueryRewriteResponse(
            success=False,
            original_query=request.query,
            rewritten_query=request.query,  # Fallback to original
            error=str(e)
        )


@app.post("/contracts/preprocess", response_model=SpecificContractPreprocessResponse)
async def preprocess_specific_contracts(request: SpecificContractPreprocessRequest):
    """
    Preprocess specific contracts by their addresses to generate enhanced ABIs.
    This endpoint allows selective preprocessing of individual contracts.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        
        agent_instance = await get_agent()
        
        # Load all available contracts
        all_contracts = agent_instance.load_zircuit_contracts()
        
        if not all_contracts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No contracts data found. Please ensure contracts file exists."
            )
        
        # Find contracts matching the requested addresses
        contracts_to_process = []
        for contract in all_contracts:
            if contract.get('address') in request.contract_addresses:
                contracts_to_process.append(contract)
        
        # Check which addresses were not found
        found_addresses = {c.get('address') for c in contracts_to_process}
        missing_addresses = set(request.contract_addresses) - found_addresses
        
        if missing_addresses:
            logger.warning(f"Contract addresses not found: {missing_addresses}")
        
        # Check if contracts already have enhanced ABIs (unless force reprocess)
        if not request.force_reprocess:
            enhanced_abis = agent_instance.load_enhanced_abis()
            already_processed = []
            remaining_contracts = []
            
            for contract in contracts_to_process:
                addr = contract.get('address')
                if addr in enhanced_abis:
                    already_processed.append({
                        "address": addr,
                        "contract_id": contract.get('id', 'unknown'),
                        "status": "already_processed"
                    })
                else:
                    remaining_contracts.append(contract)
            
            contracts_to_process = remaining_contracts
            
            if already_processed:
                logger.info(f"Skipping {len(already_processed)} already processed contracts")
        
        # Process the contracts
        processed_contracts = []
        failed_contracts = []
        
        for contract in contracts_to_process:
            try:
                contract_address = contract.get('address', 'unknown')
                contract_id = contract.get('id', 'unknown')
                
                logger.info(f"Processing specific contract: {contract_id} at {contract_address}")
                
                result_path = await agent_instance.process_contract(contract)
                
                if result_path:
                    processed_contracts.append({
                        "address": contract_address,
                        "contract_id": contract_id,
                        "status": "processed",
                        "enhanced_abi_path": result_path
                    })
                else:
                    failed_contracts.append({
                        "address": contract_address,
                        "contract_id": contract_id,
                        "status": "failed",
                        "error": "Processing returned None"
                    })
                    
            except Exception as e:
                failed_contracts.append({
                    "address": contract.get('address', 'unknown'),
                    "contract_id": contract.get('id', 'unknown'),
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(f"Failed to process contract {contract.get('id')}: {e}")
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        # Prepare response message
        total_requested = len(request.contract_addresses)
        total_processed = len(processed_contracts)
        total_failed = len(failed_contracts)
        total_missing = len(missing_addresses)
        
        if request.force_reprocess:
            message = f"Processed {total_processed}/{total_requested} contracts"
        else:
            total_skipped = total_requested - total_processed - total_failed - total_missing
            message = f"Processed {total_processed}, failed {total_failed}, skipped {total_skipped}, missing {total_missing} contracts"
        
        if failed_contracts:
            message += f". {len(failed_contracts)} contracts failed processing."
        
        return SpecificContractPreprocessResponse(
            success=total_failed == 0 and total_missing == 0,
            message=message,
            processed_contracts=processed_contracts,
            failed_contracts=failed_contracts + [
                {"address": addr, "status": "not_found", "error": "Contract address not found in dataset"}
                for addr in missing_addresses
            ],
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Specific contract preprocessing failed: {e}")
        return SpecificContractPreprocessResponse(
            success=False,
            message="Preprocessing failed",
            processed_contracts=[],
            failed_contracts=[],
            error=str(e)
        )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Zircuit Smart Contract LLM Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "POST /query": "Process natural language queries (main endpoint)",
            "POST /query/rewrite": "Rewrite natural language queries",
            "POST /preprocess": "Bulk preprocess contracts to generate enhanced ABIs",
            "POST /contracts/preprocess": "Preprocess specific contracts by address",
            "POST /contracts/select": "Stage 1: Select relevant contracts",
            "POST /functions/generate": "Stage 2: Generate function calls",
            "GET /contracts": "List available contracts",
            "GET /health": "Health check"
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn
    
    # Load environment variables
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    ) 
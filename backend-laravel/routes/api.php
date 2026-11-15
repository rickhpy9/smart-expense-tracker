<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\CategoryController;
use App\Http\Controllers\Api\ReceiptController;
use App\Http\Controllers\Api\TransactionController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Public Routes
|--------------------------------------------------------------------------
*/
Route::prefix('auth')->group(function () {
    Route::post('/register', [AuthController::class, 'register']);
    Route::post('/login', [AuthController::class, 'login']);
});

/*
|--------------------------------------------------------------------------
| Protected Routes (Sanctum)
|--------------------------------------------------------------------------
*/
Route::middleware('auth:sanctum')->group(function () {
    // Auth profile & logout
    Route::prefix('auth')->group(function () {
        Route::get('/me', [AuthController::class, 'me']);
        Route::post('/logout', [AuthController::class, 'logout']);
    });

    // Categories
    Route::get('/categories', [CategoryController::class, 'index']);

    // Transactions ML Insights
    Route::get('/transactions/insights', [TransactionController::class, 'insights']);

    // Transactions CRUD
    Route::apiResource('transactions', TransactionController::class);

    // Receipts OCR Scanning
    Route::post('/receipts/scan', [ReceiptController::class, 'scan']);
});

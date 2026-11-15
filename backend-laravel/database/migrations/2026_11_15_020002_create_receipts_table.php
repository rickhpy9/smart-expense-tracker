<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('receipts', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->string('image_path');
            $table->string('merchant_name')->nullable();
            $table->date('receipt_date')->nullable();
            $table->decimal('subtotal', 15, 2)->nullable();
            $table->decimal('tax', 15, 2)->nullable();
            $table->decimal('total_amount', 15, 2)->nullable();
            $table->float('confidence_score')->default(0);
            $table->enum('processing_status', ['pending', 'processed', 'failed'])->default('pending');
            $table->longText('raw_ocr_text')->nullable();
            $table->json('ocr_raw_payload')->nullable();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('receipts');
    }
};

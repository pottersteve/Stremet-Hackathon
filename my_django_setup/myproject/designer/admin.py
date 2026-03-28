from django.contrib import admin
from .models import (
    ManufacturingPlan, ManufacturingStep,
    QualityChecklistItem, StepMaterial, StepDependency,
)


class ManufacturingStepInline(admin.StackedInline):
    model = ManufacturingStep
    extra = 1


@admin.register(ManufacturingPlan)
class ManufacturingPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'designer', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'order__order_id')
    inlines = [ManufacturingStepInline]


class QualityChecklistItemInline(admin.TabularInline):
    model = QualityChecklistItem
    extra = 1


class StepMaterialInline(admin.TabularInline):
    model = StepMaterial
    extra = 1


class StepDependencyFromInline(admin.TabularInline):
    model = StepDependency
    fk_name = 'from_step'
    extra = 0
    verbose_name = 'Outgoing dependency'
    verbose_name_plural = 'Outgoing dependencies'


@admin.register(ManufacturingStep)
class ManufacturingStepAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan', 'status', 'sequence_order')
    list_filter = ('status',)
    search_fields = ('name', 'plan__name')
    inlines = [QualityChecklistItemInline, StepMaterialInline, StepDependencyFromInline]


@admin.register(QualityChecklistItem)
class QualityChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('description', 'step', 'result_status')
    list_filter = ('result_status',)


@admin.register(StepMaterial)
class StepMaterialAdmin(admin.ModelAdmin):
    list_display = ('material_name', 'step', 'quantity', 'unit', 'storage_location')
    search_fields = ('material_name',)


@admin.register(StepDependency)
class StepDependencyAdmin(admin.ModelAdmin):
    list_display = ('from_step', 'to_step')

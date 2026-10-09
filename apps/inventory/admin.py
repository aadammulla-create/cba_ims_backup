from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import AssetCategory, Brand, Asset, EquipmentType


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'asset_count', 'created_at')
    search_fields = ('name', 'category__name')
    list_filter = ('category', 'is_active')

    def asset_count(self, obj):
        return obj.assets.count()
    asset_count.short_description = 'Assigned Assets'


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'equipment_type_count', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)

    def equipment_type_count(self, obj):
        return obj.equipment_types.count()
    equipment_type_count.short_description = 'Equipment Types'


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        'asset_code', 'item_name', 'category', 'equipment_type',
        'brand', 'property_number', 'department', 'condition', 'status'
    )
    search_fields = (
        'asset_code', 'item_name', 'property_number',
        'serial_number', 'brand__name', 'model', 'equipment_type__name'
    )
    list_filter = ('category', 'equipment_type', 'status', 'condition', 'department', 'brand')
    actions = ['review_suggested_equipment_types']
    readonly_fields = ('asset_code', 'uuid', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            for field in ('status', 'department', 'current_location'):
                if field not in readonly:
                    readonly.append(field)
        return readonly

    def save_model(self, request, obj, form, change):
        if change:
            orig = Asset.objects.get(pk=obj.pk)
            obj.status = orig.status
            obj.department = orig.department
            obj.current_location = orig.current_location
        super().save_model(request, obj, form, change)

    fieldsets = (
        ('System Identification', {
            'fields': ('asset_code', 'uuid', 'created_by')
        }),
        ('Basic Information', {
            'fields': ('item_name', 'category', 'equipment_type', 'brand', 'model', 'description')
        }),
        ('Identifiers', {
            'fields': ('property_number', 'serial_number')
        }),
        ('Location & Custody', {
            'fields': ('department', 'current_location')
        }),
        ('Acquisition & Valuation', {
            'fields': ('acquisition_date', 'acquisition_cost', 'supplier')
        }),
        ('Condition & Status', {
            'fields': ('condition', 'status', 'remarks')
        }),
        ('Media', {
            'fields': ('asset_image',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.action(description="Review suggested equipment types for selected unassigned assets (Dry-run)")
    def review_suggested_equipment_types(self, request, queryset):
        unassigned = queryset.filter(equipment_type__isnull=True)
        if not unassigned.exists():
            self.message_user(
                request,
                "All selected assets already have an assigned Equipment Type.",
                level=messages.INFO
            )
            return

        suggestions = []
        for asset in unassigned:
            available_types = EquipmentType.objects.filter(category=asset.category, is_active=True)
            matched_type = None
            for eq_type in available_types:
                if eq_type.name.lower() in asset.item_name.lower() or eq_type.name.lower() in (asset.model or '').lower():
                    matched_type = eq_type
                    break
            suggestion_str = f"'{matched_type.name}'" if matched_type else "No match found (select manually)"
            suggestions.append(f"{asset.asset_code} ({asset.item_name}) -> Suggested: {suggestion_str}")

        msg_body = "SUGGESTED EQUIPMENT TYPES FOR MANUAL REVIEW (No automatic changes made):\n" + "\n".join(suggestions[:10])
        if len(suggestions) > 10:
            msg_body += f"\n... and {len(suggestions) - 10} more."
        self.message_user(request, msg_body, level=messages.WARNING)

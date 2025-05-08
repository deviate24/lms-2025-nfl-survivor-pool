from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.urls import reverse
from .models import Profile

# Define an inline admin descriptor for Profile model
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

# Define a new User admin with first and last name prominently displayed
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email'), 'classes': ('wide',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Register Profile separately if needed
admin.site.register(Profile)

# Add LogEntry to the admin interface in Authentication and Authorization section
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'
    list_filter = ['user', 'content_type']
    search_fields = ['object_repr', 'change_message']
    list_display = ['action_time', 'user', 'content_type', 'action_flag_display', 'object_link', 'change_message']
    readonly_fields = [
        'action_time', 'user', 'content_type', 'object_id', 'object_repr', 
        'action_flag', 'change_message', 'object_link'
    ]
    
    def action_flag_display(self, obj):
        flags = {
            1: "Addition",
            2: "Change",
            3: "Deletion"
        }
        return flags.get(obj.action_flag, "Unknown")
    action_flag_display.short_description = 'Action'
    
    def object_link(self, obj):
        if obj.action_flag == 3:  # Deletion
            return obj.object_repr
        
        try:
            ct = ContentType.objects.get_for_id(obj.content_type_id)
            if obj.object_id:
                link = reverse(f'admin:{ct.app_label}_{ct.model}_change', args=[obj.object_id])
                return format_html('<a href="{}">{}</a>', link, obj.object_repr)
            return obj.object_repr
        except:
            return obj.object_repr
    object_link.short_description = 'Object'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# Register with admin site
admin.site.register(LogEntry, LogEntryAdmin)

#!/usr/bin/env python
# coding: utf-8

# # GTM Manager for Evidon Consent Mapping
# 

# Written by Reece McWalter (rmcwalter@merkleinc.com)    
# Version: v0.0     
# Organisation: Merkle Inc.     
# Written on 26.6.2020   
# https://gtm-manager.readthedocs.io/en/latest/   
# https://pypi.org/project/gtm-manager/   
# https://developers.google.com/tag-manager/api/v1/macro-dictionary-reference

# #### __1. Import dependencies__

# In[1]:


import re
import copy
from ratelimit import limits
import gtm_manager
from gtm_manager.manager import GTMManager
from gtm_manager.account import GTMAccount
from gtm_manager.container import GTMContainer
from gtm_manager.trigger import GTMTrigger
from gtm_manager.workspace import GTMWorkspace


# #### __2. Authorise GTM API__

# In[2]:


gtm_manager.CLIENT_SECRET_FILE = "client_secret.json"
gtm_manager.CREDENTIALS_FILE_NAME = "auth_credentials.json"
gtm_manager.AUTH_SCOPES = [
    gtm_manager.GoogleTagManagerScopes.EDIT_CONTAINERS,
    gtm_manager.GoogleTagManagerScopes.PUBLISH,
    gtm_manager.GoogleTagManagerScopes.EDIT_CONTAINERVERSIONS,
]
try:
    account = GTMAccount(path="accounts/6001493098")
except: 
    print("Error: Issue finding account")
    
try:
    container = GTMContainer(path="accounts/6001493098/containers/31768050")
    print("Active Container: ",container)
    print("Auth Successful")
except: 
    print("Error: Issue finding container, auth failed")




# #### 3. Define workspace name
# If the workspace name does not exist, it will be created and set active.        
# If the workspace name does exist, it will be set active.

# In[3]:


workspace_name = "Hello"


# #### 4. Check workspace for existing

# In[4]:


def check_workspace(workspace_name):
    global workspace
    
    try:
        workspaces = container.list_workspaces(refresh=True)
    except:
        print("Error: could not find workspace")
    
    str_workspaces = []
    print("Workspaces Available:")
    for workspace in workspaces:
        entry = str(workspace)
        entry = re.search(': (.+?)>', entry)
        entry = entry.group(1)
        str_workspaces.append(entry)
        
        print(
            str(str_workspaces.index(entry))+". "+entry
        )
        
    if workspace_name in str_workspaces: 
        index = str_workspaces.index(workspace_name)
        path = workspaces[index].path
        workspace = GTMWorkspace(path=path)
        print('Workspace already exists - Using: ',workspace_name)
    else:
        print('Creating new workspace - Using: ',workspace_name)
        workspace = container.create_workspace(workspace_name)


# In[10]:


check_workspace(workspace_name)


# #### 5. Create Evidon Assets
# This will create Evidon assets necessary for implementation.
# These include:    
# 
# **Variables:**  
# - MPX - DLV - consentCategories
#         dataLayer variable name: consentCategories
#         
# 
# **Triggers**
# - Evidon Blocking - {{triggerType}} - {{trackingCategory}}    
# 
# Where triggerType may equal:
# - Page View
# - DOM Ready
# - Window Loaded
# - All Elements
# - Just Links
# - Element Visibility
# - Form Submission
# - Scroll Depth
# - Custom Event
# 
# And trackingCategory may equal:
# - Analytics
# - M&A
# - Functional
# - undefined (in the case where no consent is given)

# In[6]:


var_evidon_consent_cat ={
        "name": "MPX - DLV - consentCategories",
        "type": "v",
        "parameter": [
            {
                "value": "2",
                "key": "dataLayerVersion",
                "type": "integer"
            },
            {
                "value": "false",
                "key": "setDefaultValue",
                "type": "boolean"
            },
            {
                "value": "consentCategories TEST  ONLY",
                "key": "name",
                "type": "template"
            }
        ],
    }

try:
    workspace.create_variable(var_evidon_consent_cat)
    print(var_evidon_consent_cat["name"]+" was writted to workspace"+workspace_name)
except: 
    print("Error: Writing variable failed. Perhaps the variable already exists or check your API quota")


# In[7]:


# Define all trigger types in GTM & all consent categories in Evidon
trigger_types = ["formSubmission", "customEvent", "pageview", "windowLoaded", "click", "domReady", "elementVisibility", "linkClick", "historyChange", "youtubeVideo"]
consent_types = ["analytics", "marketing & advertising", "functional", "undefined"]

# Define generic trigger template to be used for all writes
generic_trigger={
    "type": "",
    "name": "Evidon Consent Blocking",
    "filter": [
        {
            "parameter": [
                {
                    "type": "template",
                    "value": "{{MPV - DLV - consentCategory}}",
                    "key": "arg0"
                },
                {
                    "type": "template",
                    "value": "",
                    "key": "arg1"
                },
                {
                    "type": "boolean",
                    "value": "true",
                    "key": "ignore_case"
                },
                {
                    "type": "boolean",
                    "value": "true",
                    "key": "negate"
                }
            ],
            "type": "matchRegex"
        }
    ]
}

# Define key:value for customEventFilter - This key is required for customEvent triggers
custom_event_key = "customEventFilter"  
custom_event_value=[
        {
            "parameter": [
                {
                    "type": "template",
                    "value": "{{_event}}",
                    "key": "arg0"
                },
                {
                    "type": "template",
                    "value": ".*",
                    "key": "arg1"
                },
                {
                    "type": "boolean",
                    "value": "true",
                    "key": "ignore_case"
                }
            ],
            "type": "matchRegex"
        }
]


# In[8]:


@limits(calls=10, period=1)
def collect_triggers():
    count = 0
    
    # Loop trigger types
    for trigger_type in trigger_types:
        # Reset template
        trigger = copy.deepcopy(generic_trigger)
        
        # For each trigger type, loop consent types
        for consent_type in consent_types:
            # Set dynamic parameters to template
            trigger['type'] = trigger_type
            trigger['name'] = ("Evidon Consent Blocking - "+trigger_type+" - "+consent_type).title() 
            
            # Where consent is not 'undefined', add '/|all/' to regex firing condition 
            if consent_type != 'undefined':
                trigger['filter'][0]["parameter"][1]['value'] = consent_type+"|all"
            else:
                trigger['filter'][0]["parameter"][1]['value'] = consent_type
                
            # For customEvent, create new customEvent template from original and insert key 'customEventFilter' to template             
            if trigger_type != 'customEvent':
                None
            else:  
                trigger[custom_event_key] = custom_event_value
            
            # Write to GTM
            workspace.create_trigger(trigger)
            
            # Update counter
            count = count + 1
            
            # Print condition of write
            print(str(count) + ". " + trigger['name'] + " successfuly created")


# In[9]:


collect_triggers()


# # Appendix: Dictionary for request bodies
# 
# #### 1. Variable Body:
# ```
# var_body = 
#         {
#             "name": "cjs.randomNumber",
#             "type": "jsm",
#             "parameter": [
#                 {
#                     "type": "TEMPLATE",
#                     "key": "javascript",
#                     "value": "function() {\n  return Math.random();\n}",
#                 }
#             ],
#         }
# ```
# 
# 
# 
# #### 2. Trigger Body:
# ```
# {
#     "type": {{event_type}},
#     "name": "Evidon Consent Blocking - ",{{trigger_type}}," - ",{{consent_type}},",
#     "filter": [
#         {
#             "parameter": [
#                 {
#                     "type": "template",
#                     "value": "{{MPV - DLV - consentCategory}}",
#                     "key": "arg0"
#                 },
#                 {
#                     "type": "template",
#                     "value": ",{{consentType}},"|all",
#                     "key": "arg1"
#                 },
#                 {
#                     "type": "boolean",
#                     "value": "true",
#                     "key": "ignore_case"
#                 },
#                 {
#                     "type": "boolean",
#                     "value": "true",
#                     "key": "negate"
#                 }
#             ],
#             "type": "matchRegex"
#         }
#     ]
# }
# 
# ```
# 
# #### 3. Tag Body:
# ```
#        {
#             "name": "HTML - Hello Log",
#             "type": "html",
#             "parameter": [
#                 {
#                     "type": "TEMPLATE",
#                     "key": "html",
#                     "value": '<script>\n  console.log("Hello World")\n</script>',
#                 }
#             ],
#             "firingTriggerId": [trigger.triggerId],
#         }
# ```
# 
# 
# 
# #### 4. Naming conventions
# Blocking Trigger names should be populated as:
# 'Evidon Blocking {{trigger_type}} - {{consetType}}'
# 
# ###### 4a. triggerType:  
# **Custom Event:** customEvent  
# **Page View:** pageview  
# **Window Loaded:** windowLoaded  
# **Click:** click  
# **DOM Ready:** domReady  
# **Element Visibility:** elementVisibility  
# **Form Submission:** formSubmission  
# **Link Click:** linkClick  
# **History Change:** historyChange  
# **YouTube Video:** youTubeVideo
# 
# ##### 4b consentType:  
# **No Analytics:**  
# **No M&A:**  
# **No Functional:**  
# **No Other:**  
#  _**Essential** - Must be included_ 

# In[ ]:


# 01-JUL-2020: Debug in progress (rmcwalter@merkleinc.com)


def check_var(var_to_write):
    vars = workspace.list_variables(refresh=True)
    test_var = var_to_write["parameter"]
    
    for var in vars:
        existing_params = []
        existing_params_list = var.parameter
        for params in existing_params_list:
            existing_params.append(params.to_obj())
        
        # NOTE: need to figure out way to SORT paramters before comparing
        #https://stackoverflow.com/questions/7828867/how-to-efficiently-compare-two-unordered-lists-not-sets-in-python
            
        if existing_params != test_var:
            print("creating variable...")
            workspace.create_variable(var_to_write)
            print(var_to_write," created")
        else:
            print ("variable already exists")

    


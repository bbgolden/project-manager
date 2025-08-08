PROJECT_MAKER_OUTPUT = """
The user has created a new project with the following parameters:
- Project Name: {project_name}
- Project Description: {project_desc}
"""

REQ_MAKER_OUTPUT = """
The user has created a new project requirement with the following parameters:
- Belongs to project with Project Name: {project_name}
- Requirement Description: {req_desc}
"""

TASK_MAKER_OUTPUT = """
The user has created a new task with the following parameters:
- Belongs to project with Project Name: {project_name}
- Task Name: {task_name}
- Task Desc: {task_desc}
- Start Date: {start}
- End Date {end}
"""

DEP_MAKER_OUTPUT = """
The user has created a new task dependency with the following parameters:
- First Task Name: {task1_name}
- Second Task Name: {task2_name}
- {task2_name} is dependent upon the completion of {task1_name}
- Dependency Description: {dep_desc}
"""

RES_MAKER_OUTPUT = """
The user has created a new resource with the following parameters:
- First Name: {first}
- Last Name: {last}
- Contact: {contact} 
"""

RES_ASSIGN_OUTPUT = """
The user has assigned a resource to a task with the following parameters:
- Task Name: {task_name}
- Resource First Name: {first}
- Resource Last Name: {last}
- Resource Contact: {contact}
"""

ANALYST_OUTPUT = """
The user has analyzed a project with the following parameters:
- Project Name: {project_name}
"""